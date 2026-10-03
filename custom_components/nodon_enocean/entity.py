"""Classe de base des entités NodOn EnOcean."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .device import NodOnDevice


class NodOnEntity(Entity):
    """Entité rattachée à un produit NodOn."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _state_keys: frozenset[str] = frozenset()
    # Les entités de réglage restent disponibles même si le produit est muet.
    _follows_availability = True

    def __init__(self, device: NodOnDevice, key: str) -> None:
        self.device = device
        self._attr_unique_id = f"{device.id_str}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device.id_str)})
        self._last_available = True

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.device.add_listener(self._handle_update))

    @property
    def available(self) -> bool:
        return not self._follows_availability or self.device.available

    @callback
    def _handle_update(self, keys: set[str]) -> None:
        availability_changed = False
        if self._follows_availability:
            now = self.device.available
            availability_changed = now != self._last_available
            self._last_available = now
        if not self._state_keys or keys & self._state_keys:
            self._on_state(keys)
            self.async_write_ha_state()
        elif availability_changed:
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


class NodOnConfigEntity(NodOnEntity, RestoreEntity):
    """Réglage d'un produit : catégorie Configuration, valeur restaurée au démarrage.

    Les produits ne permettent pas de relire leurs réglages : on conserve la
    dernière valeur envoyée dans l'état de l'entité.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _follows_availability = False
    _setting: str

    def __init__(self, device: NodOnDevice, setting: str) -> None:
        super().__init__(device, setting)
        self._setting = setting
        self._attr_translation_key = setting
        self._state_keys = frozenset({f"setting:{setting}"})

    def _restore(self, state: str) -> Any:
        """Convertit l'état restauré en valeur de réglage (None = ignorer)."""
        return state

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in ("unknown", "unavailable"):
            value = self._restore(last.state)
            if value is not None:
                self.device.settings[self._setting] = value
