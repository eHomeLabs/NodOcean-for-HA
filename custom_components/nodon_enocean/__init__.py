"""Intégration NodOn EnOcean pour Home Assistant."""

from __future__ import annotations

import asyncio
from collections import deque
import logging
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_integration

from . import features
from .catalog import PRODUCTS
from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_PATH,
    CONF_MODEL,
    CONF_MQTT_ADVANCED,
    CONF_MQTT_DISCOVERY,
    CONF_SENDER_OFFSET,
    DOMAIN,
    POLL_INTERVAL,
    SUBENTRY_DEVICE,
)
from .device import AVAILABILITY_KEY, NodOnDevice
from .esp3 import id_to_str, str_to_id
from .gateway import HISTORY_SIZE, Gateway, GatewayError
from .mqtt_bridge import MqttBridge, MqttConfigError, broker_settings, mqtt_enabled

_LOGGER = logging.getLogger(__name__)

MQTT_HELP_URL = "https://github.com/eHomeLabs/NodOcean-for-HA/wiki/Pont-MQTT"
HELP_URL = "https://github.com/eHomeLabs/NodOcean-for-HA/wiki/Aide-et-d%C3%A9pannage"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.EVENT,
    Platform.IMAGE,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


@dataclass
class NodOnRuntime:
    gateway: Gateway
    devices: dict[str, NodOnDevice] = field(default_factory=dict)  # par subentry_id
    mqtt: MqttBridge | None = None


type NodOnConfigEntry = ConfigEntry[NodOnRuntime]


async def async_setup_entry(hass: HomeAssistant, entry: NodOnConfigEntry) -> bool:
    histories = hass.data.setdefault(DOMAIN, {}).setdefault("history", {})
    history = histories.setdefault(entry.entry_id, deque(maxlen=HISTORY_SIZE))
    gateway = Gateway(entry.data[CONF_DEVICE_PATH], history)
    issue_id = f"gateway_unavailable_{entry.entry_id}"
    try:
        info = await gateway.connect()
    except GatewayError as err:
        native = any(
            e.state is ConfigEntryState.LOADED
            for e in hass.config_entries.async_entries("enocean")
        )
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="native_enocean" if native else "gateway_unavailable",
            translation_placeholders={"port": entry.data[CONF_DEVICE_PATH], "error": str(err)},
            learn_more_url=HELP_URL,
        )
        raise ConfigEntryNotReady(str(err)) from err
    ir.async_delete_issue(hass, DOMAIN, issue_id)

    runtime = NodOnRuntime(gateway=gateway)
    entry.runtime_data = runtime

    # Codes de sécurité ReCom attribués aux produits (par ID, gardés même si le
    # produit est supprimé puis réappairé : il garde son code).
    code_store: Store[dict[str, str]] = Store(hass, 1, _code_store_key(entry))
    codes: dict[str, str] = await code_store.async_load() or {}

    @callback
    def _save_code(device: NodOnDevice) -> None:
        if device.recom_code is not None:
            codes[device.id_str] = f"{device.recom_code:08X}"
            hass.async_create_task(code_store.async_save(dict(codes)))

    dev_reg = dr.async_get(hass)
    hub = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"gateway_{id_to_str(info.base_id)}")},
        manufacturer="EnOcean",
        name="Clé EnOcean",
        model=info.description or "USB300 / TCM310",
        sw_version=info.app_version,
        serial_number=id_to_str(info.chip_id) if info.chip_id else None,
    )

    pending_areas: dict[str, str] = hass.data.setdefault(DOMAIN, {}).setdefault(
        "pending_areas", {}
    )
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_DEVICE:
            continue
        product = PRODUCTS.get(subentry.data[CONF_MODEL])
        if product is None:
            _LOGGER.warning("Modèle inconnu : %s", subentry.data[CONF_MODEL])
            continue
        device = NodOnDevice(
            gateway,
            product,
            str_to_id(subentry.data[CONF_DEVICE_ID]),
            subentry.data.get(CONF_SENDER_OFFSET),
            subentry_id,
            subentry.title,
        )
        if (saved := codes.get(device.id_str)) is not None:
            device.recom_code = int(saved, 16)
        device.state["recom_secured"] = device.recom_code is not None
        device.on_code_change = _save_code
        device.start()
        runtime.devices[subentry_id] = device
        dev_entry = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            config_subentry_id=subentry_id,
            identifiers={(DOMAIN, device.id_str)},
            manufacturer="NodOn",
            model=product.name_fr
            if hass.config.language.startswith("fr")
            else product.name_en,
            model_id=product.references,
            name=subentry.title,
            serial_number=device.id_str,
            via_device=(DOMAIN, f"gateway_{id_to_str(info.base_id)}"),
            configuration_url=product.manual or product.url,
        )
        # Pièce choisie lors de l'ajout : appliquée une seule fois, à la création.
        area_id = pending_areas.pop(device.id_str, None)
        if (
            area_id
            and dev_entry.area_id is None
            and ar.async_get(hass).async_get_area(area_id)
        ):
            dev_reg.async_update_device(dev_entry.id, area_id=area_id)
    del hub

    @callback
    def _on_disconnect() -> None:
        if entry.state.recoverable:
            hass.config_entries.async_schedule_reload(entry.entry_id)

    gateway.on_disconnect = _on_disconnect

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _poll(_now=None) -> None:
        for device in list(runtime.devices.values()):
            if device.product.is_actuator:
                await device.refresh()
                await asyncio.sleep(0.2)

    async def _startup() -> None:
        for device in list(runtime.devices.values()):
            if device.product.is_actuator:
                await device.query_info()
                if device.product.metering:
                    await device.configure_reporting()
                await asyncio.sleep(0.2)
        await _poll()
        for device in list(runtime.devices.values()):
            if device.product.model not in features.RECOM:
                continue
            # Produit sans code : on lui en attribue un s'il vient d'être mis sous
            # tension (fenêtre de 15 min), sinon le bouton Déverrouiller le fera.
            if device.recom_code is None:
                try:
                    await device.unlock_recom()
                except GatewayError as err:
                    _LOGGER.debug("Code ReCom de %s non attribué : %s", device.title, err)
            # Volet : type d'interrupteur et temps calibrés (Remote Commissioning)
            if device.product.model in features.ROLLER_SHUTTER:
                try:
                    await device.rs_read_config()
                except GatewayError as err:
                    _LOGGER.debug("Lecture ReCom de %s impossible : %s", device.title, err)

    @callback
    def _check_availability(_now=None) -> None:
        for device in runtime.devices.values():
            if device.settings.get("timeout"):
                device.notify({AVAILABILITY_KEY})

    entry.async_on_unload(
        async_track_time_interval(hass, _poll, timedelta(seconds=POLL_INTERVAL))
    )
    entry.async_on_unload(
        async_track_time_interval(hass, _check_availability, timedelta(seconds=60))
    )
    entry.async_create_background_task(hass, _startup(), "nodon_enocean_initial_poll")
    await _async_start_mqtt(hass, entry, info)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_start_mqtt(hass: HomeAssistant, entry: NodOnConfigEntry, info) -> None:
    """Démarre le pont MQTT s'il est activé. Une erreur ne bloque jamais l'intégration."""
    issue_id = f"mqtt_config_{entry.entry_id}"
    if not mqtt_enabled(entry.options):
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return
    base_id = id_to_str(info.base_id)
    try:
        settings = broker_settings(hass, dict(entry.options), f"nodocean-{base_id.lower()}")
    except MqttConfigError as err:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"mqtt_{err}",
            learn_more_url=MQTT_HELP_URL,
        )
        return
    ir.async_delete_issue(hass, DOMAIN, issue_id)
    integration = await async_get_integration(hass, DOMAIN)
    bridge = MqttBridge(
        hass,
        settings,
        entry.runtime_data.devices,
        {
            "version": str(integration.version),
            "gateway": base_id,
            "base_topic": settings.base_topic,
            "language": hass.config.language,
        },
        entry.runtime_data.gateway,
    )
    entry.runtime_data.mqtt = bridge
    await bridge.async_start()


async def _async_update_listener(hass: HomeAssistant, entry: NodOnConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _code_store_key(entry: ConfigEntry) -> str:
    return f"{DOMAIN}.recom_codes.{entry.entry_id}"


async def async_remove_entry(hass: HomeAssistant, entry: NodOnConfigEntry) -> None:
    await Store(hass, 1, _code_store_key(entry)).async_remove()
    ir.async_delete_issue(hass, DOMAIN, f"gateway_unavailable_{entry.entry_id}")
    ir.async_delete_issue(hass, DOMAIN, f"mqtt_config_{entry.entry_id}")
    hass.data.get(DOMAIN, {}).get("history", {}).pop(entry.entry_id, None)


async def async_unload_entry(hass: HomeAssistant, entry: NodOnConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        runtime = entry.runtime_data
        if runtime.mqtt is not None:
            # Découverte désactivée (ou pont arrêté) dans les options : on retire
            # les produits du Home Assistant distant.
            adv = entry.options.get(CONF_MQTT_ADVANCED) or {}
            keep = mqtt_enabled(entry.options) and bool(adv.get(CONF_MQTT_DISCOVERY))
            await runtime.mqtt.async_stop(
                clear_discovery=runtime.mqtt.settings.discovery and not keep
            )
            runtime.mqtt = None
        runtime.gateway.on_disconnect = None
        for device in runtime.devices.values():
            device.stop()
        runtime.gateway.close()
    return unloaded
