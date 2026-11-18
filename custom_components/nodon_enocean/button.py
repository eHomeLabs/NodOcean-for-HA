"""Boutons : énergie, aide, Remote Commissioning, calibration, export pour Ocean2MQTT."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from homeassistant.components import persistent_notification

from . import NodOnConfigEntry, features
from .catalog import SUPPORT_URL
from .const import CONF_DEVICE_PATH, DOMAIN
from .device import NodOnDevice
from .entity import NodOnEntity, add_per_subentry
from .esp3 import id_to_str
from .gateway import GatewayError

# Fichier écrit dans le dossier de configuration de Home Assistant
EXPORT_FILE = "nodocean_export_ocean2mqtt.json"
# Ajoute le dépôt d'add-ons Ocean2MQTT à Home Assistant (lien My Home Assistant)
ADDON_REPOSITORY_URL = (
    "https://my.home-assistant.io/redirect/supervisor_add_addon_repository/"
    "?repository_url=https%3A%2F%2Fgithub.com%2FeHomeLabs%2Fhassio-ocean2mqtt"
)


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
    async_add_entities([NodOnExportOcean2MQTT(entry)])


def build_ocean2mqtt_export(hass: HomeAssistant, entry: NodOnConfigEntry) -> dict[str, Any]:
    """Produits appairés au format d'import d'Ocean2MQTT (codes ReCom compris)."""
    gateway = entry.runtime_data.gateway
    base_id = id_to_str(gateway.info.base_id) if gateway.info else entry.unique_id
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)
    devices = []
    for device in entry.runtime_data.devices.values():
        area = None
        if (dev := dev_reg.async_get_device(identifiers={(DOMAIN, device.id_str)})) and \
                dev.area_id and (found := area_reg.async_get_area(dev.area_id)):
            area = found.name
        devices.append({
            "id": device.id_str,
            "model": device.product.model,
            "name": device.title,
            "area": area,
            "sender_offset": device.sender_offset,
            "recom_code": f"{device.recom_code:08X}" if device.recom_code is not None else None,
            "recom_pending": bool(device.recom_pending),
        })
    return {
        "format": "ocean2mqtt-import",
        "version": 1,
        "source": "NodOcean for HA",
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "gateway": {"base_id": base_id, "port": entry.data.get(CONF_DEVICE_PATH)},
        "devices": devices,
    }


class NodOnExportOcean2MQTT(ButtonEntity):
    """Écrit le fichier d'export pour reprendre les produits dans Ocean2MQTT."""

    _attr_has_entity_name = True
    _attr_translation_key = "export_ocean2mqtt"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:export"

    def __init__(self, entry: NodOnConfigEntry) -> None:
        self._entry = entry
        gateway = entry.runtime_data.gateway
        base_id = id_to_str(gateway.info.base_id) if gateway.info else entry.unique_id
        self._attr_unique_id = f"gateway_{base_id}_export_ocean2mqtt"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"gateway_{base_id}")})

    async def async_press(self) -> None:
        data = build_ocean2mqtt_export(self.hass, self._entry)
        path = self.hass.config.path(EXPORT_FILE)

        def _write() -> None:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2, ensure_ascii=False)

        await self.hass.async_add_executor_job(_write)
        lang = self.hass.config.language or "en"
        count = len(data["devices"])
        if lang.startswith("fr"):
            title = "Export pour Ocean2MQTT"
            text = (
                f"{count} produit(s) exporté(s) dans `{EXPORT_FILE}` (dossier de "
                "configuration de Home Assistant).\n\n"
                f"- **Installer l'add-on Ocean2MQTT** : [ajouter le dépôt]({ADDON_REPOSITORY_URL}).\n"
                "- **Add-on Ocean2MQTT** : rien à faire, il reprend vos produits directement "
                "(Réglages → Migration et sauvegarde).\n"
                "- **Ocean2MQTT sur une autre machine** : récupérez ce fichier (Samba, File "
                "editor…) puis importez-le dans Ocean2MQTT (Réglages → Importer un fichier "
                "d'export NodOcean).\n\n"
                "Pour garder vos actionneurs sans les réappairer, utilisez la **même clé "
                "EnOcean** et **désactivez NodOcean for HA** avant de démarrer Ocean2MQTT : "
                "une clé ne peut être utilisée que par un seul logiciel.\n\n"
                "Ce fichier contient les codes Remote Commissioning de vos produits : ne le "
                "partagez pas."
            )
        elif lang.startswith("de"):
            title = "Export für Ocean2MQTT"
            text = (
                f"{count} Gerät(e) in `{EXPORT_FILE}` exportiert (Home-Assistant-"
                "Konfigurationsordner).\n\n"
                f"- **Ocean2MQTT-Add-on installieren**: [Repository hinzufügen]({ADDON_REPOSITORY_URL}).\n"
                "- **Ocean2MQTT-Add-on**: nichts zu tun, es übernimmt Ihre Geräte direkt "
                "(Einstellungen → Migration und Sicherung).\n"
                "- **Ocean2MQTT auf einem anderen Rechner**: Datei holen (Samba, File editor…) "
                "und in Ocean2MQTT importieren.\n\n"
                "Um Aktoren nicht neu anzulernen: **denselben EnOcean-Stick** verwenden und "
                "**NodOcean for HA deaktivieren**, bevor Ocean2MQTT startet.\n\n"
                "Die Datei enthält die Remote-Commissioning-Codes: nicht weitergeben."
            )
        else:
            title = "Export for Ocean2MQTT"
            text = (
                f"{count} device(s) exported to `{EXPORT_FILE}` (Home Assistant configuration "
                "folder).\n\n"
                f"- **Install the Ocean2MQTT add-on**: [add the repository]({ADDON_REPOSITORY_URL}).\n"
                "- **Ocean2MQTT add-on**: nothing to do, it takes your devices over directly "
                "(Settings → Migration and backup).\n"
                "- **Ocean2MQTT on another machine**: fetch this file (Samba, File editor…) and "
                "import it in Ocean2MQTT (Settings → Import a NodOcean export file).\n\n"
                "To keep your actuators without re-pairing, use the **same EnOcean stick** and "
                "**disable NodOcean for HA** before starting Ocean2MQTT: a stick can only be "
                "used by one program at a time.\n\n"
                "This file contains your devices' Remote Commissioning codes: do not share it."
            )
        persistent_notification.async_create(
            self.hass, text, title=title, notification_id="nodon_export_ocean2mqtt"
        )


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
