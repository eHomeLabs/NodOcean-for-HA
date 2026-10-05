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
