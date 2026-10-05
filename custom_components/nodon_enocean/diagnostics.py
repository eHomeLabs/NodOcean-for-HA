"""Diagnostics téléchargeables (Paramètres → Appareils et services → ⋮ → Télécharger les diagnostics)."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.loader import async_get_integration

from . import NodOnConfigEntry
from .const import CONF_MQTT_PASSWORD, CONF_MQTT_USERNAME, DOMAIN
from .device import NodOnDevice
from .esp3 import id_to_str


def _device_info(device: NodOnDevice, subentry_data: dict[str, Any]) -> dict[str, Any]:
    product = device.product
    return {
        "title": device.title,
        "model": product.model,
        "references": product.references,
        "eep": product.eep,
        "teach_in": product.teach_in,
        "enocean_id": device.id_str,
        "sender_offset": device.sender_offset,
        "subentry_data": subentry_data,
        "state": {k: v for k, v in device.state.items() if not k.startswith("_")},
        "settings": device.settings,
        "last_dbm": device.last_dbm,
        "seconds_since_last_message": round(time.monotonic() - device.last_seen, 1),
        "available": device.available,
    }


def _telegrams(entry: NodOnConfigEntry, device_id: str | None = None) -> list[dict]:
    history = list(entry.runtime_data.gateway.history)
    if device_id is None:
        return history
    return [t for t in history if device_id in (t["sender"], t["destination"])]


def _mqtt_info(entry: NodOnConfigEntry) -> dict[str, Any]:
    bridge = entry.runtime_data.mqtt
    return {
        "options": async_redact_data(
            dict(entry.options), {CONF_MQTT_PASSWORD, CONF_MQTT_USERNAME}
        ),
        "running": bridge is not None,
        "connected": bridge.connected if bridge else False,
        "broker": f"{bridge.settings.host}:{bridge.settings.port}" if bridge else None,
        "base_topic": bridge.settings.base_topic if bridge else None,
        "last_error": bridge.last_error if bridge else None,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NodOnConfigEntry
) -> dict[str, Any]:
    integration = await async_get_integration(hass, DOMAIN)
    gateway = entry.runtime_data.gateway
    info = gateway.info
    devices = []
    for subentry_id, device in entry.runtime_data.devices.items():
        devices.append(_device_info(device, dict(entry.subentries[subentry_id].data)))
    return {
        "integration_version": str(integration.version),
        "home_assistant_language": hass.config.language,
        "native_enocean_entries": len(hass.config_entries.async_entries("enocean")),
        "gateway": {
            "port": gateway.port,
            "base_id": id_to_str(info.base_id) if info else None,
            "chip_id": id_to_str(info.chip_id) if info and info.chip_id else None,
            "app_version": info.app_version if info else None,
            "description": info.description if info else None,
            "duplicates_ignored": gateway.duplicates,
        },
        "mqtt": _mqtt_info(entry),
        "products": devices,
        "last_telegrams": _telegrams(entry),
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: NodOnConfigEntry, device: dr.DeviceEntry
) -> dict[str, Any]:
    ident = next((i for d, i in device.identifiers if d == DOMAIN), None)
    for subentry_id, nodon in entry.runtime_data.devices.items():
        if nodon.id_str == ident:
            return {
                "integration_version": str((await async_get_integration(hass, DOMAIN)).version),
                "product": _device_info(nodon, dict(entry.subentries[subentry_id].data)),
                "last_telegrams": _telegrams(entry, ident),
            }
    # La clé elle-même
    return await async_get_config_entry_diagnostics(hass, entry)
