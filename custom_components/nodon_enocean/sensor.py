"""Capteurs : température, humidité, puissance, énergie, batterie, signal."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NodOnConfigEntry
from .device import NodOnDevice
from .entity import NodOnEntity, add_per_subentry


@dataclass(frozen=True, kw_only=True)
class NodOnSensorDescription(SensorEntityDescription):
    models: frozenset[str] = frozenset()
    metering: bool = False


SENSORS: tuple[NodOnSensorDescription, ...] = (
    NodOnSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        models=frozenset({"STP-2", "STPH-2"}),
    ),
    NodOnSensorDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        models=frozenset({"STPH-2"}),
    ),
    NodOnSensorDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        metering=True,
    ),
    NodOnSensorDescription(
        key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        metering=True,
    ),
    NodOnSensorDescription(
        key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        models=frozenset({"PIR-2"}),
    ),
    NodOnSensorDescription(
        key="voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        models=frozenset({"PIR-2"}),
    ),
    NodOnSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        models=frozenset({"TSB-2"}),
    ),
)

# Mesure -> réglage de correction (number.py)
OFFSETS = {"temperature": "temperature_offset", "humidity": "humidity_offset"}

RSSI = SensorEntityDescription(
    key="rssi",
    translation_key="rssi",
    device_class=SensorDeviceClass.SIGNAL_STRENGTH,
    native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NodOnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    def factory(device: NodOnDevice) -> list:
        entities: list[SensorEntity] = [
            NodOnSensor(device, desc)
            for desc in SENSORS
            if device.product.model in desc.models
            or (desc.metering and device.product.metering)
        ]
        entities.append(NodOnRssiSensor(device))
        if device.product.is_actuator:
            entities.append(NodOnFirmwareSensor(device))
        return entities

    add_per_subentry(entry.runtime_data.devices.values(), async_add_entities, factory)


class NodOnSensor(NodOnEntity, SensorEntity):
    entity_description: SensorEntityDescription

    def __init__(
        self, device: NodOnDevice, description: SensorEntityDescription
    ) -> None:
        super().__init__(device, description.key)
        self.entity_description = description
        self._offset_key = OFFSETS.get(description.key)
        self._state_keys = frozenset({description.key, self._offset_key} - {None})

    @property
    def native_value(self):
        value = self.device.state.get(self.entity_description.key)
        if value is not None and self._offset_key:
            value = round(value + (self.device.settings.get(self._offset_key) or 0), 1)
        return value


class NodOnRssiSensor(NodOnEntity, SensorEntity):
    entity_description = RSSI
    _state_keys = frozenset({"rssi"})

    def __init__(self, device: NodOnDevice) -> None:
        super().__init__(device, "rssi")

    @property
    def native_value(self) -> int | None:
        return self.device.last_dbm


class NodOnFirmwareSensor(NodOnEntity, SensorEntity):
    """Version firmware renvoyée par le produit (message fabricant NodOn)."""

    _attr_translation_key = "firmware"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _state_keys = frozenset({"firmware"})
    _follows_availability = False

    def __init__(self, device: NodOnDevice) -> None:
        super().__init__(device, "firmware")

    @property
    def native_value(self) -> str | None:
        return self.device.state.get("firmware")
