"""Déclencheurs d'appareil : touches de l'interrupteur CWS-2-1 et du Soft Button."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, EVENT_BUTTON

FOUR_BUTTONS = [
    "left_up",
    "left_down",
    "right_up",
    "right_down",
    "left_up_right_up",
    "left_down_right_down",
    "left_up_right_down",
    "left_down_right_up",
    "release",
]
TWO_BUTTONS = ["up", "down", "release"]
SOFT_BUTTON = ["single", "double", "long", "long_release"]
FLOOR_SWITCH = ["press", "release"]
ALL_TYPES = set(FOUR_BUTTONS) | set(TWO_BUTTONS) | set(SOFT_BUTTON) | set(FLOOR_SWITCH)

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {vol.Required(CONF_TYPE): vol.In(ALL_TYPES)}
)


def _trigger_types(hass: HomeAssistant, device_id: str) -> list[str]:
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return []
    ident = next((i for d, i in device.identifiers if d == DOMAIN), None)
    for entry in hass.config_entries.async_entries(DOMAIN):
        runtime = getattr(entry, "runtime_data", None)
        if runtime is None:
            continue
        for nodon in runtime.devices.values():
            if nodon.id_str != ident:
                continue
            if nodon.product.model == "TSB-2":
                return SOFT_BUTTON
            if nodon.product.model == "CRC-2":
                return FOUR_BUTTONS
            if nodon.product.model == "CFS-2":
                return FLOOR_SWITCH
            if nodon.product.model == "CWS-2-1":
                return (
                    TWO_BUTTONS
                    if nodon.settings.get("buttons") == "2"
                    else FOUR_BUTTONS
                )
    return []


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    return [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: trigger_type,
        }
        for trigger_type in _trigger_types(hass, device_id)
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: EVENT_BUTTON,
            event_trigger.CONF_EVENT_DATA: {
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                CONF_TYPE: config[CONF_TYPE],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
