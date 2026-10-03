"""Événements des boutons : interrupteur CWS-2-1 et Soft Button TSB-2."""

from __future__ import annotations

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.const import CONF_DEVICE_ID, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NodOnConfigEntry
from .const import EVENT_BUTTON
from .device import NodOnDevice
from .entity import NodOnEntity, add_per_subentry

WALL_SWITCH_EVENTS = [
    "left_up",
    "left_down",
    "right_up",
    "right_down",
    "left_up_right_up",
    "left_down_right_down",
    "left_up_right_down",
    "left_down_right_up",
    "release",
    # Façade 2 boutons : une seule touche haut / bas
    "up",
    "down",
]
TWO_BUTTON_MAP = {
    "left_up": "up",
    "right_up": "up",
    "left_down": "down",
    "right_down": "down",
}
SOFT_BUTTON_EVENTS = ["single", "double", "long", "long_release"]
SOFT_REMOTE_EVENTS = [e for e in WALL_SWITCH_EVENTS if e not in ("up", "down")]
FLOOR_SWITCH_EVENTS = ["press", "release"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NodOnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    def factory(device: NodOnDevice) -> list:
        if device.product.model == "CWS-2-1":
            return [NodOnButtonEvent(device, WALL_SWITCH_EVENTS, "wall_switch")]
        if device.product.model == "TSB-2":
            return [NodOnButtonEvent(device, SOFT_BUTTON_EVENTS, "soft_button")]
        if device.product.model == "CRC-2":
            return [NodOnButtonEvent(device, SOFT_REMOTE_EVENTS, "soft_remote")]
        if device.product.model == "CFS-2":
            return [NodOnButtonEvent(device, FLOOR_SWITCH_EVENTS, "floor_switch")]
        return []

    add_per_subentry(entry.runtime_data.devices.values(), async_add_entities, factory)


class NodOnButtonEvent(NodOnEntity, EventEntity):
    _attr_device_class = EventDeviceClass.BUTTON
    _state_keys = frozenset({"event"})

    def __init__(self, device: NodOnDevice, event_types: list[str], key: str) -> None:
        super().__init__(device, key)
        self._attr_event_types = event_types
        self._attr_translation_key = key

    @callback
    def _on_state(self, keys: set[str]) -> None:
        event = self.device.state.pop("event", None)
        if (
            self.device.product.model == "CWS-2-1"
            and self.device.settings.get("buttons") == "2"
        ):
            if event != "release":
                event = TWO_BUTTON_MAP.get(event)
        if event in self._attr_event_types:
            self._trigger_event(event)
            if self.registry_entry and self.registry_entry.device_id:
                self.hass.bus.async_fire(
                    EVENT_BUTTON,
                    {CONF_DEVICE_ID: self.registry_entry.device_id, CONF_TYPE: event},
                )
