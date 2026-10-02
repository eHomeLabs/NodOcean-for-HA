"""Détecteurs d'ouverture NodOn SDO-2 / SWO-2 (D5-00-01)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import NodOnConfigEntry
from .device import NodOnDevice
from .entity import NodOnEntity, add_per_subentry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NodOnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    def factory(device: NodOnDevice) -> list:
        if device.product.eep == "D5-00-01":
            return [NodOnOpening(device)]
        return []

    add_per_subentry(entry.runtime_data.devices.values(), async_add_entities, factory)


class NodOnOpening(NodOnEntity, BinarySensorEntity, RestoreEntity):
    _attr_name = None
    _attr_device_class = BinarySensorDeviceClass.OPENING
    _state_keys = frozenset({"opening"})

    def __init__(self, device: NodOnDevice) -> None:
        super().__init__(device, "opening")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Le SWO-2 n'émet qu'au mouvement : on restaure le dernier état connu.
        if "opening" not in self.device.state and (last := await self.async_get_last_state()):
            if last.state in ("on", "off"):
                self.device.state["opening"] = last.state == "on"

    @property
    def is_on(self) -> bool | None:
        return self.device.state.get("opening")
