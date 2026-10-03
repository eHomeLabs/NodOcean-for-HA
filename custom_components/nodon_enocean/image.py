"""Visuel du produit NodOn, affiché sur la fiche de l'appareil."""

from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.components.image import ImageEntity
from homeassistant.const import EntityCategory
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
    add_per_subentry(
        entry.runtime_data.devices.values(),
        async_add_entities,
        lambda device: [NodOnProductImage(hass, device)],
    )


class NodOnProductImage(NodOnEntity, ImageEntity):
    _attr_translation_key = "product_image"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_content_type = "image/png"
    _follows_availability = False
    _state_keys = frozenset({"_none"})

    def __init__(self, hass: HomeAssistant, device: NodOnDevice) -> None:
        NodOnEntity.__init__(self, device, "product_image")
        ImageEntity.__init__(self, hass)
        self._attr_image_url = device.product.image
        self._attr_image_last_updated = datetime(2026, 1, 1, tzinfo=UTC)
