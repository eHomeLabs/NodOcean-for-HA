"""Remise à zéro du compteur d'énergie (MSP-2, SIN-2-FP-01)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from homeassistant.components import persistent_notification

from . import NodOnConfigEntry, features
from .catalog import SUPPORT_URL
from .device import NodOnDevice
from .entity import NodOnEntity, add_per_subentry
from .gateway import GatewayError


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NodOnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    def factory(device: NodOnDevice) -> list:
        entities: list[ButtonEntity] = [NodOnHelp(device)]
        if device.product.metering:
            entities.append(NodOnResetEnergy(device))
        model = device.product.model
        if model in features.RECOM:
            entities.append(NodOnReComRead(device))
            entities.append(NodOnReComUnlock(device))
        if model in features.ROLLER_SHUTTER:
            entities.extend(
                NodOnCalibrate(device, kind) for kind in ("classic", "complex", "stop")
            )
        return entities

    add_per_subentry(entry.runtime_data.devices.values(), async_add_entities, factory)


class NodOnResetEnergy(NodOnEntity, ButtonEntity):
    _attr_translation_key = "reset_energy"
    _attr_entity_category = EntityCategory.CONFIG
    _follows_availability = False
    _state_keys = frozenset({"_none"})

    def __init__(self, device: NodOnDevice) -> None:
        super().__init__(device, "reset_energy")

    async def async_press(self) -> None:
        await self.device.reset_energy()


class NodOnReComRead(NodOnEntity, ButtonEntity):
    """Relit par Remote Commissioning les télécommandes appairées (et le volet)."""

    _attr_translation_key = "recom_read"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _follows_availability = False
    _state_keys = frozenset({"_none"})

    def __init__(self, device: NodOnDevice) -> None:
        super().__init__(device, "recom_read")

    async def async_press(self) -> None:
        try:
            await self.device.read_links()
            if self.device.product.model in features.ROLLER_SHUTTER:
                await self.device.rs_read_config()
        except GatewayError as err:
            raise HomeAssistantError(f"Lecture impossible : {err}") from err


class NodOnReComUnlock(NodOnEntity, ButtonEntity):
    """Déverrouille le produit (Remote Commissioning) ou lui attribue son code."""

    _attr_translation_key = "recom_unlock"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _follows_availability = False
    _state_keys = frozenset({"_none"})

    def __init__(self, device: NodOnDevice) -> None:
        super().__init__(device, "recom_unlock")

    async def async_press(self) -> None:
        lang = self.hass.config.language or "en"
        fr, de = lang.startswith("fr"), lang.startswith("de")
        try:
            result = await self.device.unlock_recom()
        except GatewayError as err:
            status = getattr(err, "status", None)
            if status == "locked":
                text = (
                    "Le produit répond mais reste verrouillé : il a déjà un code de "
                    "sécurité. Saisissez le code de son QR code (8 caractères après "
                    "« 11Z ») via ⋮ → Reconfigurer sur la carte du produit."
                    if fr
                    else "Das Produkt antwortet, bleibt aber gesperrt: Es hat bereits einen "
                    "Sicherheitscode. Geben Sie den Code aus seinem QR-Code (8 Zeichen "
                    "nach „11Z“) über ⋮ → Neu konfigurieren ein."
                    if de
                    else "The product answers but stays locked: it already has a security "
                    "code. Enter the code from its QR code (8 characters after \"11Z\") "
                    "via ⋮ → Reconfigure on the product card."
                )
            elif status == "no_answer":
                text = (
                    "Le produit ne répond à aucune commande Remote Commissioning, même "
                    "au test Ping. Coupez puis remettez son alimentation et réessayez "
                    "dans les 15 minutes ; si l'échec persiste, envoyez les diagnostics."
                    if fr
                    else "Das Produkt antwortet auf keinen Remote-Commissioning-Befehl, "
                    "nicht einmal auf Ping. Schalten Sie es aus und wieder ein und "
                    "versuchen Sie es innerhalb von 15 Minuten erneut."
                    if de
                    else "The product does not answer any Remote Commissioning command, "
                    "not even Ping. Power it off and on again and retry within 15 minutes."
                )
            else:
                text = (
                    "Le produit n'a pas répondu. Coupez puis remettez son alimentation, "
                    "puis appuyez sur Déverrouiller dans les 15 minutes."
                    if fr
                    else "Das Produkt hat nicht geantwortet. Schalten Sie seine Stromversorgung "
                    "aus und wieder ein und drücken Sie innerhalb von 15 Minuten auf Entsperren."
                    if de
                    else "The product did not answer. Power it off and on again, then press "
                    "Unlock within 15 minutes."
                )
            raise HomeAssistantError(text) from err
        if result == "assigned":
            message = (
                "Un code de sécurité a été attribué au produit et enregistré dans Home Assistant."
                if fr
                else "Dem Produkt wurde ein Sicherheitscode zugewiesen und in Home Assistant gespeichert."
                if de
                else "A security code was assigned to the product and saved in Home Assistant."
            )
        else:
            message = (
                "Produit déverrouillé : il accepte le Remote Commissioning."
                if fr
                else "Produkt entsperrt: Remote Commissioning ist möglich."
                if de
                else "Product unlocked: Remote Commissioning is available."
            )
        persistent_notification.async_create(
            self.hass,
            f"**{self.device.title}** — {message}",
            title="Remote Commissioning",
            notification_id=f"nodon_recom_{self.device.id_str}",
        )


class NodOnCalibrate(NodOnEntity, ButtonEntity):
    """Calibration du volet SIN-2-RS-01 : classique, complexe ou arrêt."""

    _attr_entity_category = EntityCategory.CONFIG
    _follows_availability = False
    _state_keys = frozenset({"_none"})

    def __init__(self, device: NodOnDevice, kind: str) -> None:
        super().__init__(device, f"calibration_{kind}")
        self._kind = kind
        self._attr_translation_key = f"calibration_{kind}"

    async def async_press(self) -> None:
        try:
            await self.device.rs_calibrate(self._kind)
        except GatewayError as err:
            raise HomeAssistantError(f"Calibration non lancée : {err}") from err


class NodOnHelp(NodOnEntity, ButtonEntity):
    """Aide : affiche une notification avec les liens vers le support NodOn."""

    _attr_translation_key = "help"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _follows_availability = False
    _state_keys = frozenset({"_none"})

    def __init__(self, device: NodOnDevice) -> None:
        super().__init__(device, "help")

    async def async_press(self) -> None:
        product = self.device.product
        lang = self.hass.config.language or "en"
        fr = lang.startswith("fr")
        de = lang.startswith("de")
        lines = [
            f"**{product.name(lang)}** ({product.references}) — {self.device.title}",
            "",
        ]
        def t(fr_text: str, en_text: str, de_text: str) -> str:
            return fr_text if fr else de_text if de else en_text

        if product.manual:
            lines.append(
                f"- [{t('Notice du produit', 'Product user guide', 'Bedienungsanleitung')}]"
                f"({product.manual})"
            )
        lines.append(
            f"- [{t('Support NodOn (FAQ, notices)', 'NodOn support (FAQ, guides)', 'NodOn-Support (FAQ, Anleitungen)')}]"
            f"({SUPPORT_URL})"
        )
        lines.append(
            f"- [{t('Contacter le support NodOn', 'Contact NodOn support', 'NodOn-Support kontaktieren')}]"
            f"({SUPPORT_URL}/support/tickets/new)"
        )
        lines.append(f"- {t('Identifiant EnOcean', 'EnOcean ID', 'EnOcean-ID')} : `{self.device.id_str}`")
        persistent_notification.async_create(
            self.hass,
            "\n".join(lines),
            title=t("Aide NodOn", "NodOn help", "NodOn-Hilfe"),
            notification_id=f"nodon_help_{self.device.id_str}",
        )
