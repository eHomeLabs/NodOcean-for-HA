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
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
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
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        models=frozenset({"TSB-2"}),
    ),
)

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
            if device.product.model in desc.models or (desc.metering and device.product.metering)
        ]
        entities.append(NodOnRssiSensor(device))
        return entities

    add_per_subentry(entry.runtime_data.devices.values(), async_add_entities, factory)


class NodOnSensor(NodOnEntity, SensorEntity):
    entity_description: SensorEntityDescription

    def __init__(self, device: NodOnDevice, description: SensorEntityDescription) -> None:
        super().__init__(device, description.key)
        self.entity_description = description
        self._state_keys = frozenset({description.key})

    @property
    def native_value(self):
        return self.device.state.get(self.entity_description.key)


class NodOnRssiSensor(NodOnEntity, SensorEntity):
    entity_description = RSSI
    _state_keys = frozenset({"rssi"})

    def __init__(self, device: NodOnDevice) -> None:
        super().__init__(device, "rssi")

    @property
    def native_value(self) -> int | None:
        return self.device.last_dbm
