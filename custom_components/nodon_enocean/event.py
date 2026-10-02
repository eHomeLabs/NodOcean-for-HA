"""Événements des boutons : interrupteur CWS-2-1 et Soft Button TSB-2."""

from __future__ import annotations

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NodOnConfigEntry
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
]
SOFT_BUTTON_EVENTS = ["single", "double", "long", "long_release"]


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
        if event in self._attr_event_types:
            self._trigger_event(event)
