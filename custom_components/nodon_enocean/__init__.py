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
from homeassistant.loader import async_get_integration

from .catalog import PRODUCTS
from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_PATH,
    CONF_MODEL,
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
        },
    )
    entry.runtime_data.mqtt = bridge
    await bridge.async_start()


async def _async_update_listener(hass: HomeAssistant, entry: NodOnConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: NodOnConfigEntry) -> None:
    ir.async_delete_issue(hass, DOMAIN, f"gateway_unavailable_{entry.entry_id}")
    ir.async_delete_issue(hass, DOMAIN, f"mqtt_config_{entry.entry_id}")
    hass.data.get(DOMAIN, {}).get("history", {}).pop(entry.entry_id, None)


async def async_unload_entry(hass: HomeAssistant, entry: NodOnConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        runtime = entry.runtime_data
        if runtime.mqtt is not None:
            await runtime.mqtt.async_stop()
            runtime.mqtt = None
        runtime.gateway.on_disconnect = None
        for device in runtime.devices.values():
            device.stop()
        runtime.gateway.close()
    return unloaded
