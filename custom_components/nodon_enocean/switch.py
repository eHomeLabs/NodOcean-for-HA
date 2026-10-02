"""Relais / prises NodOn (D2-01-xx)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NodOnConfigEntry
from .device import NodOnDevice
from .entity import NodOnEntity, add_per_subentry

SWITCH_MODELS = {
    "SIN-2-1-01": None,
    "ASP-2": SwitchDeviceClass.OUTLET,
    "MSP-2": SwitchDeviceClass.OUTLET,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NodOnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    def factory(device: NodOnDevice) -> list:
        if device.product.model in SWITCH_MODELS:
            return [NodOnSwitch(device, SWITCH_MODELS[device.product.model])]
        return []

    add_per_subentry(entry.runtime_data.devices.values(), async_add_entities, factory)


class NodOnSwitch(NodOnEntity, SwitchEntity):
    _attr_name = None
    _state_keys = frozenset({"output_0"})

    def __init__(self, device: NodOnDevice, device_class: SwitchDeviceClass | None) -> None:
        super().__init__(device, "switch")
        self._attr_device_class = device_class

    @property
    def is_on(self) -> bool | None:
        return self.device.state.get("output_0")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.device.set_output(0, True)
        self.device.state["output_0"] = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.device.set_output(0, False)
        self.device.state["output_0"] = False
        self.async_write_ha_state()
