"""Module éclairage 2 canaux NodOn SIN-2-2-01 (D2-01-12)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NodOnConfigEntry
from .device import NodOnDevice
from .entity import NodOnEntity, add_per_subentry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NodOnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    def factory(device: NodOnDevice) -> list:
        if device.product.model == "SIN-2-2-01":
            return [NodOnLight(device, ch) for ch in range(device.product.channels)]
        return []

    add_per_subentry(entry.runtime_data.devices.values(), async_add_entities, factory)


class NodOnLight(NodOnEntity, LightEntity):
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_translation_key = "channel"

    def __init__(self, device: NodOnDevice, channel: int) -> None:
        super().__init__(device, f"light_{channel}")
        self._channel = channel
        self._key = f"output_{channel}"
        self._state_keys = frozenset({self._key})
        self._attr_translation_placeholders = {"channel": str(channel + 1)}

    @property
    def is_on(self) -> bool | None:
        return self.device.state.get(self._key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.device.set_output(self._channel, True)
        self.device.state[self._key] = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.device.set_output(self._channel, False)
        self.device.state[self._key] = False
        self.async_write_ha_state()
