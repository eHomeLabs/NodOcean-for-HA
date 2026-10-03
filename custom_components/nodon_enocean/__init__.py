"""Intégration NodOn EnOcean pour Home Assistant."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval

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
from .gateway import Gateway, GatewayError

_LOGGER = logging.getLogger(__name__)

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


type NodOnConfigEntry = ConfigEntry[NodOnRuntime]


async def async_setup_entry(hass: HomeAssistant, entry: NodOnConfigEntry) -> bool:
    gateway = Gateway(entry.data[CONF_DEVICE_PATH])
    try:
        info = await gateway.connect()
    except GatewayError as err:
        raise ConfigEntryNotReady(str(err)) from err

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
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: NodOnConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NodOnConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        runtime = entry.runtime_data
        runtime.gateway.on_disconnect = None
        for device in runtime.devices.values():
            device.stop()
        runtime.gateway.close()
    return unloaded
