"""Classe de base des entités NodOn EnOcean."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .device import NodOnDevice


class NodOnEntity(Entity):
    """Entité rattachée à un produit NodOn."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _state_keys: frozenset[str] = frozenset()

    def __init__(self, device: NodOnDevice, key: str) -> None:
        self.device = device
        self._attr_unique_id = f"{device.id_str}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device.id_str)})

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.device.add_listener(self._handle_update))

    @callback
    def _handle_update(self, keys: set[str]) -> None:
        if not self._state_keys or keys & self._state_keys:
            self._on_state(keys)
            self.async_write_ha_state()

    @callback
    def _on_state(self, keys: set[str]) -> None:
        """Hook pour les entités qui réagissent à un événement."""


def add_per_subentry(
    devices: Iterable[NodOnDevice],
    async_add_entities: AddConfigEntryEntitiesCallback,
    factory: Callable[[NodOnDevice], list[Entity]],
) -> None:
    for device in devices:
        entities = factory(device)
        if entities:
            async_add_entities(entities, config_subentry_id=device.subentry_id)
