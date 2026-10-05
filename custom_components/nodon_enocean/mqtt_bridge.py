"""Pont MQTT (NodOcean to MQTT) : publie l'état des produits et reçoit des commandes.

Le pont est facultatif et s'ajoute à l'intégration : si le broker est injoignable,
Home Assistant continue de fonctionner normalement.

Topics (base = « nodocean » par défaut) :
- <base>/bridge/state         online / offline (message de dernière volonté)
- <base>/bridge/info          version, clé, liste des produits (JSON)
- <base>/<produit>            état du produit (JSON)
- <base>/<produit>/availability  online / offline (délai d'indisponibilité)
- <base>/<produit>/action     appui de bouton (non conservé)
- <base>/<produit>/set        commandes (JSON ou ON / OFF / TOGGLE)
- <base>/<produit>/get        demande de relecture de l'état
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import ssl
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .const import (
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
    DEFAULT_BASE_TOPIC,
    DEFAULT_DISCOVERY_PREFIX,
    TOPIC_NAME_ID,
)
from .device import AVAILABILITY_KEY, PILOT_WIRE_MODES, REPEATER_LEVELS, NodOnDevice
from .gateway import Gateway, GatewayError

if TYPE_CHECKING:
    import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)

# Façade 2 boutons de l'interrupteur mural (même logique que event.py)
_TWO_BUTTON_MAP = {
    "left_up": "up",
    "right_up": "up",
    "left_down": "down",
    "right_down": "down",
}
_ON = {"ON", "1", "TRUE"}
_OFF = {"OFF", "0", "FALSE"}


class MqttConfigError(Exception):
    """Configuration incomplète (ex. intégration MQTT de HA absente)."""


@dataclass(frozen=True)
class BrokerSettings:
    host: str
    port: int
    username: str | None
    password: str | None
    tls: bool
    tls_insecure: bool
    ca_path: str | None
    client_id: str
    base_topic: str
    topic_name: str
    retain: bool
    qos: int
    discovery: bool = False
    discovery_prefix: str = DEFAULT_DISCOVERY_PREFIX
    telegrams: bool = False


def broker_settings(
    hass: HomeAssistant, options: dict[str, Any], default_client_id: str
) -> BrokerSettings:
    """Réglages du broker à partir des options (ou de l'intégration MQTT de HA)."""
    adv = options.get(CONF_MQTT_ADVANCED) or {}
    if options.get(CONF_MQTT_USE_HA):
        entries = hass.config_entries.async_entries("mqtt")
        if not entries:
            raise MqttConfigError("no_ha_mqtt")
        data = {**entries[0].data, **entries[0].options}
        if not data.get("broker"):
            raise MqttConfigError("no_ha_mqtt")
        host = data["broker"]
        port = int(data.get("port") or 1883)
        username = data.get("username") or None
        password = data.get("password") or None
        tls = bool(data.get("certificate")) or port == 8883
        tls_insecure = bool(data.get("tls_insecure"))
        ca_path = None
    else:
        host = (options.get(CONF_MQTT_HOST) or "").strip()
        if not host:
            raise MqttConfigError("no_host")
        port = int(options.get(CONF_MQTT_PORT) or 1883)
        username = options.get(CONF_MQTT_USERNAME) or None
        password = options.get(CONF_MQTT_PASSWORD) or None
        tls = bool(options.get(CONF_MQTT_TLS))
        tls_insecure = bool(adv.get(CONF_MQTT_TLS_INSECURE))
        ca_path = (adv.get(CONF_MQTT_CA) or "").strip() or None
    base = (options.get(CONF_MQTT_BASE_TOPIC) or DEFAULT_BASE_TOPIC).strip().strip("/")
    return BrokerSettings(
        host=host,
        port=port,
        username=username,
        password=password,
        tls=tls,
        tls_insecure=tls_insecure,
        ca_path=ca_path,
        client_id=(adv.get(CONF_MQTT_CLIENT_ID) or "").strip() or default_client_id,
        base_topic=base or DEFAULT_BASE_TOPIC,
        topic_name=options.get(CONF_MQTT_TOPIC_NAME) or "name",
        retain=adv.get(CONF_MQTT_RETAIN, True),
        qos=int(adv.get(CONF_MQTT_QOS) or 0),
        discovery=bool(adv.get(CONF_MQTT_DISCOVERY)),
        discovery_prefix=(adv.get(CONF_MQTT_DISCOVERY_PREFIX) or "").strip().strip("/")
        or DEFAULT_DISCOVERY_PREFIX,
        telegrams=bool(adv.get(CONF_MQTT_TELEGRAMS)),
    )


def mqtt_enabled(options: dict[str, Any]) -> bool:
    return bool(options.get(CONF_MQTT_ENABLED))


def _new_client(settings: BrokerSettings) -> mqtt.Client:
    """Crée le client paho (appel bloquant : chargement des certificats)."""
    import paho.mqtt.client as mqtt  # noqa: PLC0415

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=settings.client_id,
        protocol=mqtt.MQTTv311,
    )
    if settings.username:
        client.username_pw_set(settings.username, settings.password)
    if settings.tls:
        client.tls_set(
            ca_certs=settings.ca_path,
            cert_reqs=ssl.CERT_NONE if settings.tls_insecure else ssl.CERT_REQUIRED,
        )
        if settings.tls_insecure:
            client.tls_insecure_set(True)
    client.reconnect_delay_set(min_delay=1, max_delay=60)
    return client


def check_connection(settings: BrokerSettings, timeout: float = 8.0) -> str | None:
    """Essaie de se connecter au broker (bloquant). Renvoie une clé d'erreur ou None."""
    import time  # noqa: PLC0415

    try:
        client = _new_client(settings)
    except (OSError, ValueError, ssl.SSLError) as err:
        _LOGGER.debug("Certificat MQTT illisible : %s", err)
        return "tls_error"
    result: dict[str, Any] = {}

    def _on_connect(_c, _u, _f, reason_code, _p) -> None:
        result["rc"] = reason_code

    client.on_connect = _on_connect
    try:
        client.connect(settings.host, settings.port, keepalive=10)
    except ssl.SSLError as err:
        _LOGGER.debug("Erreur TLS MQTT : %s", err)
        return "tls_error"
    except OSError as err:
        _LOGGER.debug("Broker MQTT injoignable : %s", err)
        return "cannot_connect"
    deadline = time.monotonic() + timeout
    try:
        while "rc" not in result and time.monotonic() < deadline:
            client.loop(timeout=0.2)
    except ssl.SSLError:
        return "tls_error"
    except OSError:
        return "cannot_connect"
    finally:
        try:
            client.disconnect()
        except Exception:  # noqa: BLE001
            pass
    rc = result.get("rc")
    if rc is None:
        return "cannot_connect"
    if rc.is_failure:
        # 4 / 5 (MQTT 3.1.1) : identifiant ou mot de passe refusé
        return "invalid_auth" if rc.value in (4, 5, 134, 135) else "cannot_connect"
    return None


# -- Conversion état <-> JSON ----------------------------------------------------


def device_payload(device: NodOnDevice) -> dict[str, Any]:
    """État d'un produit tel que publié sur MQTT."""
    product = device.product
    state = device.state
    out: dict[str, Any] = {}
    if product.channels > 1:
        for ch in range(product.channels):
            if (value := state.get(f"output_{ch}")) is not None:
                out[f"state_l{ch + 1}"] = "ON" if value else "OFF"
    elif product.eep.startswith("D2-01") and product.eep != "D2-01-0C":
        if (value := state.get("output_0")) is not None:
            out["state"] = "ON" if value else "OFF"
    if product.eep == "D2-05-00" and "position" in state:
        pos = state["position"]
        out["position"] = pos
        if pos is not None:
            out["state"] = "CLOSED" if pos == 0 else "OPEN"
    if (mode := state.get("pilot_wire_mode")) is not None and mode < len(PILOT_WIRE_MODES):
        out["mode"] = PILOT_WIRE_MODES[mode]
    for key in ("power", "energy", "illuminance", "voltage", "battery", "firmware"):
        if state.get(key) is not None:
            out[key] = state[key]
    for key, offset in (("temperature", "temperature_offset"), ("humidity", "humidity_offset")):
        if state.get(key) is not None:
            out[key] = round(state[key] + (device.settings.get(offset) or 0), 1)
    for key, name in (("opening", "open"), ("motion", "motion"), ("card", "card")):
        if state.get(key) is not None:
            out[name] = bool(state[key])
    if (level := state.get("repeater")) is not None and level < len(REPEATER_LEVELS):
        out["repeater"] = REPEATER_LEVELS[level]
    if device.last_dbm is not None:
        out["rssi"] = device.last_dbm
    return out


def _parse_switch(value: Any, current: bool | None) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value).strip().upper()
    if text in _ON:
        return True
    if text in _OFF:
        return False
    if text == "TOGGLE":
        return not current
    return None


async def apply_command(device: NodOnDevice, command: dict[str, Any]) -> list[str]:
    """Exécute une commande reçue sur /set. Renvoie la liste des clés ignorées."""
    product = device.product
    ignored: list[str] = []
    for key, value in command.items():
        if product.eep == "D2-05-00":
            if key == "position":
                await device.cover_position(max(0, min(100, int(value))))
                continue
            if key == "state":
                action = str(value).strip().upper()
                if action == "OPEN":
                    await device.cover_position(100)
                elif action == "CLOSE":
                    await device.cover_position(0)
                elif action == "STOP":
                    await device.cover_stop()
                else:
                    ignored.append(key)
                continue
        if product.eep == "D2-01-0C" and key == "mode":
            if value in PILOT_WIRE_MODES:
                await device.set_pilot_wire(value)
            else:
                ignored.append(key)
            continue
        channel: int | None = None
        if product.eep.startswith("D2-01") and product.eep != "D2-01-0C":
            if key == "state" and product.channels == 1:
                channel = 0
            elif key.startswith("state_l") and key[7:].isdigit():
                channel = int(key[7:]) - 1
                if not 0 <= channel < product.channels:
                    channel = None
        if channel is not None:
            on = _parse_switch(value, device.state.get(f"output_{channel}"))
            if on is None:
                ignored.append(key)
            else:
                await device.set_output(channel, on)
            continue
        ignored.append(key)
    return ignored


# -- Pont -----------------------------------------------------------------------


class MqttBridge:
    """Client MQTT de l'intégration (un par clé EnOcean)."""

    def __init__(
        self,
        hass: HomeAssistant,
        settings: BrokerSettings,
        devices: dict[str, NodOnDevice],
        info: dict[str, Any],
        gateway: Gateway | None = None,
    ) -> None:
        self.hass = hass
        self.gateway = gateway
        self.settings = settings
        self.devices = devices
        self.info = info
        self.connected = False
        self.last_error: str | None = None
        self._client: mqtt.Client | None = None
        self._unsubs: list[Callable[[], None]] = []
        self._topics: dict[str, NodOnDevice] = {}  # topic produit -> produit
        self._names: dict[str, str] = {}  # subentry_id -> topic produit
        self._available: dict[str, bool] = {}
        self._last_seen: dict[str, str] = {}
        self._discovery: dict[str, dict] = {}  # topic de configuration -> configuration

    # Topics ---------------------------------------------------------------

    def _t(self, *parts: str) -> str:
        return "/".join((self.settings.base_topic, *parts))

    def _assign_topics(self) -> None:
        used: set[str] = {"bridge"}
        for subentry_id, device in self.devices.items():
            if self.settings.topic_name == TOPIC_NAME_ID:
                name = device.id_str
            else:
                name = slugify(device.title) or device.id_str
                if name in used:
                    name = f"{name}_{device.id_str}"
            used.add(name)
            self._names[subentry_id] = name
            self._topics[name] = device

    def device_topic(self, device: NodOnDevice) -> str:
        return self._t(self._names[device.subentry_id])

    @property
    def discovery_node(self) -> str:
        return f"nodocean_{str(self.info.get('gateway', '')).lower()}"

    @property
    def _discovery_pattern(self) -> str:
        return f"{self.settings.discovery_prefix}/+/{self.discovery_node}/+/config"

    def _is_discovery_topic(self, topic: str) -> bool:
        parts = topic.split("/")
        prefix = self.settings.discovery_prefix.split("/")
        return (
            len(parts) == len(prefix) + 4
            and parts[: len(prefix)] == prefix
            and parts[-3] == self.discovery_node
            and parts[-1] == "config"
        )

    # Cycle de vie ---------------------------------------------------------

    async def async_start(self) -> None:
        self._assign_topics()
        if self.settings.discovery:
            from .mqtt_discovery import all_configs  # noqa: PLC0415

            self._discovery = all_configs(self)
        try:
            client = await self.hass.async_add_executor_job(_new_client, self.settings)
        except (OSError, ValueError, ssl.SSLError) as err:
            self.last_error = f"TLS : {err}"
            _LOGGER.error("Pont MQTT : certificat illisible (%s)", err)
            return
        client.will_set(self._t("bridge", "state"), "offline", qos=1, retain=True)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        self._client = client
        for device in self.devices.values():
            self._available[device.subentry_id] = device.available
            self._unsubs.append(
                device.add_listener(self._listener(device), first=True)
            )
        if self.settings.telegrams and self.gateway is not None:
            self._unsubs.append(self.gateway.add_record_listener(self._on_record))
        try:
            await self.hass.async_add_executor_job(
                client.connect_async, self.settings.host, self.settings.port, 60
            )
        except (OSError, ValueError) as err:
            self.last_error = str(err)
            _LOGGER.warning("Pont MQTT : %s", err)
        client.loop_start()

    async def async_stop(self, clear_discovery: bool = False) -> None:
        """Arrête le pont. clear_discovery : retire les produits du HA distant."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        client, self._client = self._client, None
        if client is None:
            return

        def _stop() -> None:
            if self.connected and clear_discovery:
                if not self._discovery:
                    from .mqtt_discovery import all_configs  # noqa: PLC0415

                    self._discovery = all_configs(self)
                for topic in self._discovery:
                    client.publish(topic, "", qos=1, retain=True)
            if self.connected:
                info = client.publish(self._t("bridge", "state"), "offline", qos=1, retain=True)
                try:
                    info.wait_for_publish(timeout=2)
                except (RuntimeError, ValueError):
                    pass
            self.connected = False  # arrêt volontaire : pas d'alerte de déconnexion
            client.disconnect()
            client.loop_stop()

        await self.hass.async_add_executor_job(_stop)
        self.connected = False

    # Callbacks paho (thread réseau) ---------------------------------------

    def _on_connect(self, client, _userdata, _flags, reason_code, _props) -> None:
        if reason_code.is_failure:
            self.connected = False
            self.last_error = str(reason_code)
            _LOGGER.warning("Pont MQTT : connexion refusée (%s)", reason_code)
            return
        self.connected = True
        self.last_error = None
        _LOGGER.info(
            "Pont MQTT connecté à %s:%s (topic %s)",
            self.settings.host,
            self.settings.port,
            self.settings.base_topic,
        )
        qos = self.settings.qos
        client.subscribe(
            [
                (self._t("+", "set"), qos),
                (self._t("+", "get"), qos),
                # Configurations de découverte déjà publiées : retirer celles en trop
                (self._discovery_pattern, 1),
            ]
        )
        for topic, config in self._discovery.items():
            client.publish(topic, json.dumps(config, ensure_ascii=False), qos=1, retain=True)
        client.publish(self._t("bridge", "state"), "online", qos=1, retain=True)
        self.hass.loop.call_soon_threadsafe(self._publish_all)

    def _on_disconnect(self, _client, _userdata, _flags, reason_code, _props) -> None:
        if self.connected:
            _LOGGER.warning("Pont MQTT déconnecté (%s), reconnexion…", reason_code)
        self.connected = False

    def _on_message(self, client, _userdata, message) -> None:
        topic = message.topic
        if self._is_discovery_topic(topic):
            # Produit supprimé ou découverte désactivée : on efface la configuration.
            if message.payload and topic not in self._discovery:
                _LOGGER.debug("Pont MQTT : retrait de la découverte %s", topic)
                client.publish(topic, "", qos=1, retain=True)
            return
        payload = bytes(message.payload)
        self.hass.loop.call_soon_threadsafe(self._handle_message, topic, payload)

    # Publication ----------------------------------------------------------

    def _publish(self, topic: str, payload: Any, retain: bool | None = None) -> None:
        if self._client is None or not self.connected:
            return
        if not isinstance(payload, str):
            payload = json.dumps(payload, ensure_ascii=False)
        self._client.publish(
            topic,
            payload,
            qos=self.settings.qos,
            retain=self.settings.retain if retain is None else retain,
        )

    @callback
    def _publish_all(self) -> None:
        devices = [
            {
                "name": device.title,
                "topic": self.device_topic(device),
                "enocean_id": device.id_str,
                "model": device.product.model,
                "references": device.product.references,
                "eep": device.product.eep,
                "actuator": device.product.is_actuator,
            }
            for device in self.devices.values()
        ]
        self._publish(self._t("bridge", "info"), {**self.info, "devices": devices}, True)
        for device in self.devices.values():
            self._publish(
                self.device_topic(device) + "/availability",
                "online" if device.available else "offline",
                True,
            )
            if device.state or device.last_dbm is not None:
                self._publish_state(device)

    def _publish_state(self, device: NodOnDevice) -> None:
        payload = device_payload(device)
        if last := self._last_seen.get(device.subentry_id):
            payload["last_seen"] = last
        payload["available"] = device.available
        self._publish(self.device_topic(device), payload)

    def _listener(self, device: NodOnDevice) -> Callable[[set[str]], None]:
        @callback
        def _update(keys: set[str]) -> None:
            topic = self.device_topic(device)
            available = device.available
            if self._available.get(device.subentry_id) != available:
                self._available[device.subentry_id] = available
                self._publish(topic + "/availability", "online" if available else "offline", True)
            if keys == {AVAILABILITY_KEY}:
                return
            if "rssi" in keys:  # un télégramme vient d'arriver
                self._last_seen[device.subentry_id] = (
                    datetime.now(timezone.utc).isoformat(timespec="seconds")
                )
            event = device.state.get("event") if "event" in keys else None
            if event:
                if device.product.model == "CWS-2-1" and device.settings.get("buttons") == "2":
                    event = _TWO_BUTTON_MAP.get(event, event)
                self._publish(topic + "/action", event, False)
            self._publish_state(device)

        return _update

    @callback
    def _on_record(self, record: dict) -> None:
        """Télégramme EnOcean brut (debug) -> <base>/bridge/telegrams."""
        payload = dict(record)
        for device in self.devices.values():
            if device.id_str in (record.get("sender"), record.get("destination")):
                payload["product"] = self._names.get(device.subentry_id)
                break
        self._publish(self._t("bridge", "telegrams"), payload, False)

    # Commandes ------------------------------------------------------------

    @callback
    def _handle_message(self, topic: str, payload: bytes) -> None:
        parts = topic.split("/")
        if len(parts) < 2:
            return
        name, verb = parts[-2], parts[-1]
        if verb not in ("set", "get"):
            return
        device = self._topics.get(name)
        if device is None:
            _LOGGER.debug("Pont MQTT : produit inconnu %s", name)
            return
        if verb == "get":
            self.hass.async_create_task(self._refresh(device))
            return
        text = payload.decode("utf-8", errors="replace").strip()
        try:
            command = json.loads(text) if text.startswith("{") else None
        except ValueError:
            command = None
        if command is None:
            if text.startswith("{"):
                _LOGGER.warning("Pont MQTT : JSON invalide sur %s : %s", topic, text)
                return
            if device.product.eep == "D2-05-00":
                command = (
                    {"position": int(text)} if text.isdigit() else {"state": text}
                )
            elif device.product.eep == "D2-01-0C":
                command = {"mode": text}
            else:
                command = {"state": text}
        self.hass.async_create_task(self._command(device, topic, command))

    async def _refresh(self, device: NodOnDevice) -> None:
        if device.product.is_actuator:
            await device.refresh()
            await asyncio.sleep(0.5)
        self._publish_state(device)

    async def _command(self, device: NodOnDevice, topic: str, command: dict) -> None:
        if not device.product.is_actuator:
            _LOGGER.warning("Pont MQTT : %s est un capteur, commande ignorée", device.title)
            return
        try:
            ignored = await apply_command(device, command)
        except (GatewayError, ValueError, TypeError) as err:
            _LOGGER.warning("Pont MQTT : commande %s sur %s impossible : %s", command, topic, err)
            return
        if ignored:
            _LOGGER.warning(
                "Pont MQTT : %s ne comprend pas %s", device.title, ", ".join(ignored)
            )
