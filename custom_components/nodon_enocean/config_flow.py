"""Assistant de configuration : clé EnOcean puis ajout guidé des produits NodOn."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.selector import (
    AreaSelector,
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .catalog import GALLERY, PRODUCTS, TEACH_UTE_BIDIR, Product
from .const import (
    CONF_AREA,
    CONF_NEW_AREA,
    CONF_DEVICE_ID,
    CONF_DEVICE_PATH,
    CONF_MODEL,
    CONF_MQTT_ADVANCED,
    CONF_MQTT_BASE_TOPIC,
    CONF_MQTT_CA,
    CONF_MQTT_CLIENT_ID,
    CONF_MQTT_DISCOVERY,
    CONF_MQTT_DISCOVERY_PREFIX,
    CONF_MQTT_ENABLED,
    CONF_MQTT_HOST,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_PORT,
    CONF_MQTT_QOS,
    CONF_MQTT_RETAIN,
    CONF_MQTT_TELEGRAMS,
    CONF_MQTT_TLS,
    CONF_MQTT_TLS_INSECURE,
    CONF_MQTT_TOPIC_NAME,
    CONF_MQTT_USE_HA,
    CONF_MQTT_USERNAME,
    CONF_SENDER_OFFSET,
    DEFAULT_BASE_TOPIC,
    DEFAULT_DISCOVERY_PREFIX,
    DOMAIN,
    TOPIC_NAME_ID,
    TOPIC_NAME_NAME,
    PAIRING_TIMEOUT,
    SUBENTRY_DEVICE,
)
from .esp3 import id_to_str, str_to_id
from .gateway import Gateway, GatewayError, GatewayOpenError
from .mqtt_bridge import MqttConfigError, broker_settings, check_connection
from .pairing import PairingResult, wait_for_teach_in

_LOGGER = logging.getLogger(__name__)

MANUAL_PATH = "manual"
MQTT_WIKI = "https://github.com/eHomeLabs/NodOcean-for-HA/wiki/Pont-MQTT"


def _list_ports() -> list[tuple[str, str]]:
    import serial.tools.list_ports  # noqa: PLC0415

    ports = []
    for port in serial.tools.list_ports.comports():
        path = port.device
        try:
            from homeassistant.components.usb import get_serial_by_id  # noqa: PLC0415

            path = get_serial_by_id(port.device)
        except Exception:  # noqa: BLE001
            pass
        label = f"{port.device} — {port.description or ''}"
        if port.manufacturer:
            label += f" ({port.manufacturer})"
        ports.append((path, label))
    return ports


async def _validate_port(path: str) -> tuple[str, Gateway]:
    gateway = Gateway(path)
    info = await gateway.connect()
    gateway.close()
    return id_to_str(info.base_id), gateway


def _error_key(err: GatewayError) -> str:
    return "cannot_open" if isinstance(err, GatewayOpenError) else "no_response"


class NodOnEnOceanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configuration de la clé EnOcean."""

    VERSION = 1

    def __init__(self) -> None:
        self._usb_path: str | None = None
        self._last_error = ""
        self._new_key: tuple[str, str] = ("", "")

    def _native_enocean_loaded(self) -> bool:
        return any(
            e.state is ConfigEntryState.LOADED
            for e in self.hass.config_entries.async_entries("enocean")
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NodOnOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_DEVICE: NodOnDeviceSubentryFlow}

    async def _create(self, path: str) -> ConfigFlowResult:
        base_id, _ = await _validate_port(path)
        await self.async_set_unique_id(base_id)
        self._abort_if_unique_id_configured(updates={CONF_DEVICE_PATH: path})
        return self.async_create_entry(
            title=f"Clé EnOcean {base_id}", data={CONF_DEVICE_PATH: path}
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            path = user_input[CONF_DEVICE_PATH]
            if path == MANUAL_PATH:
                return await self.async_step_manual()
            try:
                return await self._create(path)
            except GatewayError as err:
                errors["base"] = _error_key(err)
                self._last_error = str(err)

        if not errors and self._native_enocean_loaded():
            errors["base"] = "native_enocean"
        ports = await self.hass.async_add_executor_job(_list_ports)
        options = [SelectOptionDict(value=p, label=lbl) for p, lbl in ports]
        options.append(SelectOptionDict(value=MANUAL_PATH, label="Saisie manuelle…"))
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_PATH): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                    )
                }
            ),
            errors=errors,
            description_placeholders={"error": self._last_error},
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                return await self._create(user_input[CONF_DEVICE_PATH])
            except GatewayError as err:
                errors["base"] = _error_key(err)
                self._last_error = str(err)
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE_PATH): str}),
            errors=errors,
            description_placeholders={"error": self._last_error},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Changer le port de la clé (ou remplacer la clé) sans perdre les produits."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            path = user_input[CONF_DEVICE_PATH]
            # La clé actuelle doit être libérée avant de tester le port.
            if entry.state is ConfigEntryState.LOADED:
                await self.hass.config_entries.async_unload(entry.entry_id)
            try:
                base_id, _ = await _validate_port(path)
            except GatewayError as err:
                errors["base"] = _error_key(err)
                self._last_error = str(err)
                await self.hass.config_entries.async_setup(entry.entry_id)
            else:
                if base_id == entry.unique_id:
                    return self.async_update_reload_and_abort(
                        entry, data_updates={CONF_DEVICE_PATH: path}
                    )
                self._new_key = (path, base_id)
                # On remet l'ancienne configuration en route tant que rien n'est confirmé.
                await self.hass.config_entries.async_setup(entry.entry_id)
                return await self.async_step_reconfigure_new_key()

        ports = await self.hass.async_add_executor_job(_list_ports)
        options = [SelectOptionDict(value=p, label=lbl) for p, lbl in ports]
        current = entry.data[CONF_DEVICE_PATH]
        if current not in {p for p, _ in ports}:
            options.insert(0, SelectOptionDict(value=current, label=current))
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_PATH, default=current): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            custom_value=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            errors=errors,
            description_placeholders={"error": self._last_error, "current": current},
        )

    async def async_step_reconfigure_new_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Une autre clé a été branchée : prévenir avant de l'adopter."""
        entry = self._get_reconfigure_entry()
        path, base_id = self._new_key
        if user_input is not None:
            for other in self._async_current_entries(include_ignore=False):
                if other.entry_id != entry.entry_id and other.unique_id == base_id:
                    await self.hass.config_entries.async_setup(entry.entry_id)
                    return self.async_abort(reason="already_configured")
            return self.async_update_reload_and_abort(
                entry,
                unique_id=base_id,
                title=f"Clé EnOcean {base_id}",
                data_updates={CONF_DEVICE_PATH: path},
            )
        return self.async_show_form(
            step_id="reconfigure_new_key",
            description_placeholders={"old": entry.unique_id or "?", "new": base_id},
        )

    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        from homeassistant.components.usb import get_serial_by_id  # noqa: PLC0415

        self._usb_path = await self.hass.async_add_executor_job(
            get_serial_by_id, discovery_info.device
        )
        self._async_abort_entries_match({CONF_DEVICE_PATH: self._usb_path})
        self.context["title_placeholders"] = {"name": discovery_info.description or "USB300"}
        return await self.async_step_usb_confirm()

    async def async_step_usb_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._usb_path is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                return await self._create(self._usb_path)
            except GatewayError as err:
                errors["base"] = _error_key(err)
                self._last_error = str(err)
        self._set_confirm_only()
        return self.async_show_form(
            step_id="usb_confirm",
            description_placeholders={"path": self._usb_path, "error": self._last_error},
            errors=errors,
        )


def _mqtt_schema(o: dict[str, Any]) -> vol.Schema:
    adv = o.get(CONF_MQTT_ADVANCED) or {}
    password = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
    return vol.Schema(
        {
            vol.Required(CONF_MQTT_ENABLED, default=o.get(CONF_MQTT_ENABLED, False)): BooleanSelector(),
            vol.Required(CONF_MQTT_USE_HA, default=o.get(CONF_MQTT_USE_HA, False)): BooleanSelector(),
            vol.Optional(
                CONF_MQTT_HOST, description={"suggested_value": o.get(CONF_MQTT_HOST)}
            ): TextSelector(),
            vol.Required(CONF_MQTT_PORT, default=o.get(CONF_MQTT_PORT, 1883)): NumberSelector(
                NumberSelectorConfig(min=1, max=65535, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_MQTT_USERNAME, description={"suggested_value": o.get(CONF_MQTT_USERNAME)}
            ): TextSelector(),
            # Laissé vide : le mot de passe déjà enregistré est conservé.
            vol.Optional(CONF_MQTT_PASSWORD): password,
            vol.Required(CONF_MQTT_TLS, default=o.get(CONF_MQTT_TLS, False)): BooleanSelector(),
            vol.Required(
                CONF_MQTT_BASE_TOPIC, default=o.get(CONF_MQTT_BASE_TOPIC, DEFAULT_BASE_TOPIC)
            ): TextSelector(),
            vol.Required(
                CONF_MQTT_TOPIC_NAME, default=o.get(CONF_MQTT_TOPIC_NAME, TOPIC_NAME_NAME)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[TOPIC_NAME_NAME, TOPIC_NAME_ID],
                    mode=SelectSelectorMode.LIST,
                    translation_key="topic_name",
                )
            ),
            vol.Required(CONF_MQTT_ADVANCED): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_MQTT_RETAIN, default=adv.get(CONF_MQTT_RETAIN, True)
                        ): BooleanSelector(),
                        vol.Required(
                            CONF_MQTT_QOS, default=str(adv.get(CONF_MQTT_QOS, 0))
                        ): SelectSelector(
                            SelectSelectorConfig(
                                options=["0", "1", "2"], mode=SelectSelectorMode.DROPDOWN
                            )
                        ),
                        vol.Optional(
                            CONF_MQTT_CLIENT_ID,
                            description={"suggested_value": adv.get(CONF_MQTT_CLIENT_ID)},
                        ): TextSelector(),
                        vol.Optional(
                            CONF_MQTT_CA, description={"suggested_value": adv.get(CONF_MQTT_CA)}
                        ): TextSelector(),
                        vol.Required(
                            CONF_MQTT_TLS_INSECURE, default=adv.get(CONF_MQTT_TLS_INSECURE, False)
                        ): BooleanSelector(),
                        vol.Required(
                            CONF_MQTT_TELEGRAMS, default=adv.get(CONF_MQTT_TELEGRAMS, False)
                        ): BooleanSelector(),
                        vol.Required(
                            CONF_MQTT_DISCOVERY, default=adv.get(CONF_MQTT_DISCOVERY, False)
                        ): BooleanSelector(),
                        vol.Required(
                            CONF_MQTT_DISCOVERY_PREFIX,
                            default=adv.get(CONF_MQTT_DISCOVERY_PREFIX, DEFAULT_DISCOVERY_PREFIX),
                        ): TextSelector(),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )


class NodOnOptionsFlow(OptionsFlow):
    """Options de la clé : pont MQTT (NodOcean to MQTT)."""

    def __init__(self) -> None:
        self._error = ""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        current = dict(self.config_entry.options)
        errors: dict[str, str] = {}
        if user_input is not None:
            options = {**current, **user_input}
            options[CONF_MQTT_PORT] = int(options.get(CONF_MQTT_PORT) or 1883)
            adv = dict(options.get(CONF_MQTT_ADVANCED) or {})
            adv[CONF_MQTT_QOS] = int(adv.get(CONF_MQTT_QOS) or 0)
            options[CONF_MQTT_ADVANCED] = adv
            if not user_input.get(CONF_MQTT_PASSWORD):
                if current.get(CONF_MQTT_PASSWORD):
                    options[CONF_MQTT_PASSWORD] = current[CONF_MQTT_PASSWORD]
                else:
                    options.pop(CONF_MQTT_PASSWORD, None)
            if not (options.get(CONF_MQTT_USERNAME) or "").strip():
                options.pop(CONF_MQTT_USERNAME, None)
                options.pop(CONF_MQTT_PASSWORD, None)
            if options.get(CONF_MQTT_ENABLED):
                try:
                    settings = broker_settings(self.hass, options, "nodocean-test")
                except MqttConfigError as err:
                    errors["base"] = str(err)
                else:
                    # Identifiant distinct : ne pas déconnecter le pont déjà en route.
                    settings = replace(settings, client_id=f"{settings.client_id}-test")
                    if error := await self.hass.async_add_executor_job(
                        check_connection, settings
                    ):
                        errors["base"] = error
                        self._error = f"{settings.host}:{settings.port}"
            if not errors:
                return self.async_create_entry(data=options)
            current = options
        return self.async_show_form(
            step_id="init",
            data_schema=_mqtt_schema(current),
            errors=errors,
            description_placeholders={"broker": self._error, "wiki": MQTT_WIKI},
        )


class NodOnDeviceSubentryFlow(ConfigSubentryFlow):
    """Ajout guidé d'un produit NodOn : choix → consignes → appairage auto."""

    def __init__(self) -> None:
        self._product: Product | None = None
        self._result: PairingResult | None = None
        self._sender_offset: int | None = None
        self._task: asyncio.Task[PairingResult | None] | None = None

    @callback
    def async_remove(self) -> None:
        """Fenêtre fermée : on arrête l'écoute d'appairage."""
        if self._task is not None and not self._task.done():
            self._task.cancel()

    def _default_name(self) -> str:
        assert self._product is not None
        return f"{self._product.name(self._lang)} NodOn"

    @property
    def _lang(self) -> str:
        return self.hass.config.language or "en"

    def _known_ids(self) -> set[int]:
        ids: set[int] = set()
        for sub in self._get_entry().subentries.values():
            if CONF_DEVICE_ID in sub.data:
                ids.add(str_to_id(sub.data[CONF_DEVICE_ID]))
        return ids

    def _next_sender_offset(self) -> int:
        used = {
            sub.data[CONF_SENDER_OFFSET]
            for sub in self._get_entry().subentries.values()
            if sub.data.get(CONF_SENDER_OFFSET) is not None
        }
        for offset in range(1, 128):
            if offset not in used:
                return offset
        raise GatewayError("Plus d'identifiant d'émission disponible")

    def _placeholders(self) -> dict[str, str]:
        assert self._product is not None
        p = self._product
        image = f"![{p.model}]({p.image})\n\n" if p.image else ""
        return {
            "model": p.references,
            "name": p.name(self._lang),
            "image": image,
            "instructions": p.pairing(self._lang),
            "timeout": str(PAIRING_TIMEOUT),
        }

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        entry = self._get_entry()
        if entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="gateway_not_ready")
        if user_input is not None:
            self._product = PRODUCTS[user_input[CONF_MODEL]]
            return await self.async_step_instructions()

        options = [
            SelectOptionDict(value=p.model, label=f"{p.references} — {p.name(self._lang)}")
            for p in PRODUCTS.values()
        ]
        return self.async_show_form(
            step_id="user",
            description_placeholders={"gallery": f"![NodOn]({GALLERY})"},
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                    )
                }
            ),
        )

    async def async_step_instructions(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is not None:
            return await self.async_step_pairing()
        return self.async_show_form(
            step_id="instructions", description_placeholders=self._placeholders()
        )

    async def async_step_pairing(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        assert self._product is not None
        if self._task is None:
            gateway = self._get_entry().runtime_data.gateway
            if self._product.teach_in == TEACH_UTE_BIDIR:
                self._sender_offset = self._next_sender_offset()
            self._task = self.hass.async_create_task(
                wait_for_teach_in(
                    gateway,
                    self._product,
                    self._sender_offset,
                    PAIRING_TIMEOUT,
                    self._known_ids(),
                )
            )
        if not self._task.done():
            return self.async_show_progress(
                step_id="pairing",
                progress_action="pairing",
                description_placeholders=self._placeholders(),
                progress_task=self._task,
            )
        try:
            self._result = self._task.result()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Erreur pendant l'appairage")
            self._result = None
        self._task = None
        if self._result is None:
            return self.async_show_progress_done(next_step_id="timeout")
        return self.async_show_progress_done(next_step_id="confirm")

    async def async_step_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is not None:
            if (
                user_input.get("action") == "manual"
                and self._product
                and not self._product.is_actuator
            ):
                return await self.async_step_manual()
            return await self.async_step_instructions()
        assert self._product is not None
        actions = [SelectOptionDict(value="retry", label="retry")]
        if not self._product.is_actuator:
            actions.append(SelectOptionDict(value="manual", label="manual"))
        return self.async_show_form(
            step_id="timeout",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="retry"): SelectSelector(
                        SelectSelectorConfig(
                            options=actions,
                            mode=SelectSelectorMode.LIST,
                            translation_key="timeout_action",
                        )
                    )
                }
            ),
            description_placeholders=self._placeholders(),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                device_id = str_to_id(user_input[CONF_DEVICE_ID])
            except ValueError:
                errors[CONF_DEVICE_ID] = "invalid_id"
            else:
                if device_id in self._known_ids():
                    return self.async_abort(reason="already_configured")
                assert self._product is not None
                self._result = PairingResult(device_id, None, self._product.eep)
                return await self.async_step_confirm()
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE_ID): TextSelector()}),
            errors=errors,
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        assert self._product is not None and self._result is not None
        if user_input is not None:
            data: dict[str, Any] = {
                CONF_MODEL: self._product.model,
                CONF_DEVICE_ID: id_to_str(self._result.device_id),
            }
            if self._product.is_actuator:
                data[CONF_SENDER_OFFSET] = self._sender_offset
            area_id = user_input.get(CONF_AREA)
            if new_area := (user_input.get(CONF_NEW_AREA) or "").strip():
                area_id = ar.async_get(self.hass).async_get_or_create(new_area).id
            if area_id:
                data[CONF_AREA] = area_id
                # Appliquée à la création de l'appareil, au rechargement qui suit.
                self.hass.data.setdefault(DOMAIN, {}).setdefault("pending_areas", {})[
                    data[CONF_DEVICE_ID]
                ] = area_id
            return self.async_create_entry(
                title=user_input.get("name") or self._default_name(),
                data=data,
                unique_id=id_to_str(self._result.device_id),
            )
        placeholders = self._placeholders()
        placeholders["device_id"] = id_to_str(self._result.device_id)
        placeholders["rssi"] = f"{self._result.dbm} dBm" if self._result.dbm is not None else "—"
        placeholders["after"] = self._product.after(self._lang)
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Required("name", default=self._default_name()): str,
                    vol.Optional(CONF_AREA): AreaSelector(),
                    vol.Optional(CONF_NEW_AREA): TextSelector(),
                }
            ),
            description_placeholders=placeholders,
        )
