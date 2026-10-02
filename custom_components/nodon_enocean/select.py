"""Mode fil pilote du SIN-2-FP-01 (D2-01-0C)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NodOnConfigEntry
from .device import PILOT_WIRE_MODES, NodOnDevice
from .entity import NodOnEntity, add_per_subentry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NodOnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    def factory(device: NodOnDevice) -> list:
        if device.product.model == "SIN-2-FP-01":
            return [NodOnPilotWire(device)]
        return []

    add_per_subentry(entry.runtime_data.devices.values(), async_add_entities, factory)


class NodOnPilotWire(NodOnEntity, SelectEntity):
    _attr_translation_key = "pilot_wire_mode"
    _attr_options = PILOT_WIRE_MODES
    _state_keys = frozenset({"pilot_wire_mode"})

    def __init__(self, device: NodOnDevice) -> None:
        super().__init__(device, "pilot_wire_mode")

    @property
    def current_option(self) -> str | None:
        mode = self.device.state.get("pilot_wire_mode")
        if mode is None or mode >= len(PILOT_WIRE_MODES):
            return None
        return PILOT_WIRE_MODES[mode]

    async def async_select_option(self, option: str) -> None:
        await self.device.set_pilot_wire(option)
        self.device.state["pilot_wire_mode"] = PILOT_WIRE_MODES.index(option)
        self.async_write_ha_state()
