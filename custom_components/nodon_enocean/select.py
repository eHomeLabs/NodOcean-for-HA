"""Mode fil pilote du SIN-2-FP-01 (D2-01-0C)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import NodOnConfigEntry, eep, features
from .device import PILOT_WIRE_MODES, REPEATER_LEVELS, RS_SWITCH_TYPES, NodOnDevice
from .gateway import GatewayError
from .entity import NodOnConfigEntity, NodOnEntity, add_per_subentry

POWER_ON_STATES = ["previous", "on", "off"]
BUTTON_MODES = ["4", "2"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NodOnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    def factory(device: NodOnDevice) -> list:
        model = device.product.model
        entities: list[SelectEntity] = []
        if model == "SIN-2-FP-01":
            entities.append(NodOnPilotWire(device))
        if model in features.POWER_ON_STATE:
            entities.append(
                NodOnSettingSelect(device, "default_state", POWER_ON_STATES)
            )
        if model in features.SWITCH_TYPE:
            entities.append(NodOnSwitchTypeSelect(device))
        if model in features.ROLLER_SHUTTER:
            entities.append(NodOnRsSwitchTypeSelect(device))
        if model in features.BUTTON_MODE:
            entities.append(NodOnButtonModeSelect(device, "buttons", BUTTON_MODES))
        if device.product.is_actuator:
            entities.append(NodOnRepeater(device))
        return entities

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


class NodOnSettingSelect(NodOnConfigEntity, SelectEntity):
    """État après coupure de courant (CMD 0x2)."""

    def __init__(self, device: NodOnDevice, setting: str, options: list[str]) -> None:
        super().__init__(device, setting)
        self._attr_options = options

    def _restore(self, state: str):
        return state if state in self._attr_options else None

    @property
    def current_option(self) -> str | None:
        return self.device.settings.get(self._setting)

    async def async_select_option(self, option: str) -> None:
        await self.device.apply_local_settings(**{self._setting: option})
        self.async_write_ha_state()


class NodOnButtonModeSelect(NodOnSettingSelect):
    """Interrupteur mural : façade 2 ou 4 boutons (réglage côté Home Assistant)."""

    async def async_select_option(self, option: str) -> None:
        self.device.settings[self._setting] = option
        self.async_write_ha_state()


class NodOnRepeater(NodOnEntity, SelectEntity, RestoreEntity):
    """Niveau du répéteur EnOcean intégré (message fabricant NodOn)."""

    _attr_translation_key = "repeater"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = REPEATER_LEVELS
    _state_keys = frozenset({"repeater"})
    _follows_availability = False

    def __init__(self, device: NodOnDevice) -> None:
        super().__init__(device, "repeater")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if (
            "repeater" not in self.device.state
            and last
            and last.state in REPEATER_LEVELS
        ):
            self.device.state["repeater"] = REPEATER_LEVELS.index(last.state)

    @property
    def current_option(self) -> str | None:
        level = self.device.state.get("repeater")
        return REPEATER_LEVELS[level] if level is not None else None

    async def async_select_option(self, option: str) -> None:
        await self.device.set_repeater(option)
        self.async_write_ha_state()


class NodOnSwitchTypeSelect(NodOnSettingSelect):
    """Type d'entrée filaire des modules SIN-2-1/2 (CMD 0xB)."""

    def __init__(self, device: NodOnDevice) -> None:
        super().__init__(device, "switch_type", list(eep.SWITCH_TYPES))

    async def async_select_option(self, option: str) -> None:
        await self.device.set_switch_type(option)
        self.async_write_ha_state()


class NodOnRsSwitchTypeSelect(NodOnEntity, SelectEntity, RestoreEntity):
    """Type d'interrupteur filaire du volet SIN-2-RS-01 (Remote Commissioning)."""

    _attr_translation_key = "rs_switch_type"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = RS_SWITCH_TYPES
    _state_keys = frozenset({"rs_switch_type"})
    _follows_availability = False

    def __init__(self, device: NodOnDevice) -> None:
        super().__init__(device, "rs_switch_type")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if "rs_switch_type" not in self.device.state and last and last.state in RS_SWITCH_TYPES:
            self.device.state["rs_switch_type"] = last.state

    @property
    def current_option(self) -> str | None:
        return self.device.state.get("rs_switch_type")

    async def async_select_option(self, option: str) -> None:
        try:
            await self.device.rs_set_switch_type(option)
        except GatewayError as err:
            raise HomeAssistantError(f"Réglage non appliqué : {err}") from err
        self.async_write_ha_state()
