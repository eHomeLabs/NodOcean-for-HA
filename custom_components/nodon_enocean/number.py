"""Réglages numériques : temporisations des actionneurs, corrections des capteurs."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NodOnConfigEntry, eep, features
from .device import NodOnDevice
from .entity import NodOnConfigEntity, add_per_subentry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NodOnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    def factory(device: NodOnDevice) -> list:
        model = device.product.model
        entities: list[NumberEntity] = []
        for kind, models in (
            ("auto_off", features.AUTO_OFF),
            ("delay_off", features.DELAY_OFF),
        ):
            if model in models:
                entities.extend(
                    NodOnTimer(device, kind, ch)
                    for ch in range(device.product.channels)
                )
        if model in features.TEMPERATURE_OFFSET:
            entities.append(
                NodOnOffset(device, "temperature_offset", UnitOfTemperature.CELSIUS, 5)
            )
        if model in features.HUMIDITY_OFFSET:
            entities.append(NodOnOffset(device, "humidity_offset", PERCENTAGE, 20))
        if model in features.TIMEOUT:
            entities.append(NodOnTimeout(device))
        if model in features.ROLLER_SHUTTER:
            entities.append(NodOnTravelTime(device))
        return entities

    add_per_subentry(entry.runtime_data.devices.values(), async_add_entities, factory)


class _NodOnNumber(NodOnConfigEntity, NumberEntity):
    _attr_mode = NumberMode.BOX

    def _restore(self, state: str) -> float | None:
        try:
            return float(state)
        except ValueError:
            return None

    @property
    def native_value(self) -> float:
        return self.device.settings[self._setting]


class NodOnTimer(_NodOnNumber):
    """Extinction automatique / extinction radio retardée (CMD 0xB), par canal."""

    _attr_native_min_value = 0
    _attr_native_max_value = 3600
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    @property
    def native_value(self) -> int:
        return int(self.device.settings[self._setting])

    def __init__(self, device: NodOnDevice, kind: str, channel: int) -> None:
        super().__init__(device, f"{kind}_{channel}")
        self._kind = kind
        self._channel = channel
        if device.product.channels > 1:
            self._attr_translation_key = f"{kind}_channel"
            self._attr_translation_placeholders = {"channel": str(channel + 1)}
        else:
            self._attr_translation_key = kind

    async def async_set_native_value(self, value: float) -> None:
        await self.device.set_timer(self._channel, self._kind, value)
        self.async_write_ha_state()


class NodOnOffset(_NodOnNumber):
    """Correction appliquée à la mesure (côté Home Assistant uniquement)."""

    _attr_native_step = 0.1

    def __init__(
        self, device: NodOnDevice, setting: str, unit: str, limit: float
    ) -> None:
        super().__init__(device, setting)
        self._attr_native_unit_of_measurement = unit
        self._attr_native_min_value = -limit
        self._attr_native_max_value = limit

    async def async_set_native_value(self, value: float) -> None:
        self.device.settings[self._setting] = value
        self.async_write_ha_state()
        self.device.notify({self._setting})


class NodOnTimeout(_NodOnNumber):
    """Délai sans message avant de marquer le capteur indisponible (0 = jamais)."""

    _attr_native_min_value = 0
    _attr_native_max_value = 1440
    _attr_native_step = 5
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, device: NodOnDevice) -> None:
        super().__init__(device, "timeout")

    async def async_set_native_value(self, value: float) -> None:
        self.device.settings[self._setting] = int(value)
        self.async_write_ha_state()
        self.device.notify({self._setting})


class NodOnTravelTime(_NodOnNumber):
    """Temps de course du volet (D2-05 CMD 0x5), montée = descente.

    Remplace la calibration automatique ; le module considère ensuite le volet
    ouvert (0 %) : le mettre en haut avant de régler.
    """

    _attr_native_min_value = eep.TRAVEL_TIME_MIN
    _attr_native_max_value = eep.TRAVEL_TIME_MAX
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(self, device: NodOnDevice) -> None:
        super().__init__(device, "travel_time")

    @property
    def native_value(self) -> float | None:
        value = self.device.settings.get("travel_time") or 0
        return value or None

    async def async_set_native_value(self, value: float) -> None:
        await self.device.set_travel_time(value)
        self.async_write_ha_state()
