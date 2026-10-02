"""Module volet roulant NodOn SIN-2-RS-01 (D2-05-00)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
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
        if device.product.model == "SIN-2-RS-01":
            return [NodOnCover(device)]
        return []

    add_per_subentry(entry.runtime_data.devices.values(), async_add_entities, factory)


class NodOnCover(NodOnEntity, CoverEntity):
    _attr_name = None
    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _state_keys = frozenset({"position"})

    def __init__(self, device: NodOnDevice) -> None:
        super().__init__(device, "cover")
        self._target: int | None = None

    @property
    def current_cover_position(self) -> int | None:
        return self.device.state.get("position")

    @property
    def is_closed(self) -> bool | None:
        pos = self.current_cover_position
        return None if pos is None else pos == 0

    @property
    def is_opening(self) -> bool:
        pos = self.current_cover_position
        return self._target is not None and pos is not None and self._target > pos

    @property
    def is_closing(self) -> bool:
        pos = self.current_cover_position
        return self._target is not None and pos is not None and self._target < pos

    @callback
    def _on_state(self, keys: set[str]) -> None:
        # Le module renvoie sa position à l'arrêt : le mouvement est terminé.
        self._target = None

    async def _go(self, position: int) -> None:
        await self.device.cover_position(position)
        self._target = position
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._go(100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._go(0)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        await self._go(int(kwargs[ATTR_POSITION]))

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self.device.cover_stop()
        self._target = None
        self.async_write_ha_state()
