"""Pont MQTT (NodOcean to MQTT) : options, publication des états, commandes."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from custom_components.nodon_enocean.const import DOMAIN

from .test_integration import CWS, SIN21, STPH, _pair, _setup_gateway

OK = SimpleNamespace(is_failure=False, value=0)


class FakeClient:
    """Remplace paho : enregistre les publications, simule la connexion."""

    instances: list[FakeClient] = []

    def __init__(self, settings) -> None:
        self.settings = settings
        self.published: list[tuple[str, str, bool]] = []
        self.subscribed: list = []
        self.will = None
        self.connected_to = None
        self.stopped = False
        self.on_connect = self.on_disconnect = self.on_message = None
        FakeClient.instances.append(self)

    def will_set(self, topic, payload, qos=0, retain=False):
        self.will = (topic, payload, retain)

    def connect_async(self, host, port, keepalive):
        self.connected_to = (host, port)

    def loop_start(self):
        self.on_connect(self, None, None, OK, None)

    def loop_stop(self):
        self.stopped = True

    def disconnect(self):
        pass

    def subscribe(self, topics):
        self.subscribed.extend(topics)

    def publish(self, topic, payload, qos=0, retain=False):
        self.published.append((topic, payload, retain))
        return SimpleNamespace(wait_for_publish=lambda timeout=None: None)

    def last(self, topic):
        for t, p, _ in reversed(self.published):
            if t == topic:
                return p
        return None

    def receive(self, hass, topic, payload: str):
        self.on_message(self, None, SimpleNamespace(topic=topic, payload=payload.encode()))


OPTIONS = {
    "mqtt_enabled": True,
    "mqtt_use_ha": False,
    "mqtt_host": "192.168.1.20",
    "mqtt_port": 1883,
    "mqtt_username": "nodon",
    "mqtt_password": "secret",
    "mqtt_tls": False,
    "mqtt_base_topic": "nodocean",
    "mqtt_topic_name": "name",
    "advanced": {"mqtt_retain": True, "mqtt_qos": "0", "mqtt_tls_insecure": False},
}


async def _configure(hass, entry, user_input, check=None):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "init"
    with patch(
        "custom_components.nodon_enocean.config_flow.check_connection",
        return_value=check,
    ) as checked:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input
        )
    await hass.async_block_till_done()
    return result, checked


async def test_mqtt_bridge(hass: HomeAssistant, dongle) -> None:
    FakeClient.instances.clear()
    entry = await _setup_gateway(hass)
    entry = await _pair(
        hass, entry, dongle, "SIN-2-1-01",
        lambda: dongle.inject(0xD4, bytes.fromhex("A0 01 46 00 0F 01 D2"), SIN21),
        "Lampe salon",
    )
    entry = await _pair(
        hass, entry, dongle, "STPH-2",
        lambda: dongle.inject(0xA5, bytes.fromhex("00 00 00 00"), STPH),
        "Capteur chambre",
    )
    entry = await _pair(
        hass, entry, dongle, "CWS-2-1",
        lambda: dongle.inject(0xF6, bytes.fromhex("30"), CWS),
        "Interrupteur entrée",
    )
    assert entry.runtime_data.mqtt is None

    with patch("custom_components.nodon_enocean.mqtt_bridge._new_client", FakeClient):
        # Broker injoignable : erreur, rien n'est enregistré
        result, _ = await _configure(hass, entry, OPTIONS, check="cannot_connect")
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}
        assert not entry.options

        result, checked = await _configure(hass, entry, OPTIONS)
        assert result["type"] is FlowResultType.CREATE_ENTRY
        settings = checked.call_args.args[0]
        assert settings.client_id.endswith("-test")
        assert entry.options["mqtt_password"] == "secret"
        assert entry.options["advanced"]["mqtt_qos"] == 0

        bridge = entry.runtime_data.mqtt
        assert bridge is not None and bridge.connected
        client = FakeClient.instances[-1]
        assert client.connected_to == ("192.168.1.20", 1883)
        assert client.settings.username == "nodon"
        assert client.settings.client_id == "nodocean-ff8a2c00"
        assert client.will == ("nodocean/bridge/state", "offline", True)
        assert client.last("nodocean/bridge/state") == "online"
        assert ("nodocean/+/set", 0) in client.subscribed

        info = json.loads(client.last("nodocean/bridge/info"))
        assert info["version"] == "0.5.0" and info["gateway"] == "FF8A2C00"
        topics = {d["name"]: d["topic"] for d in info["devices"]}
        assert topics["Lampe salon"] == "nodocean/lampe_salon"
        assert topics["Capteur chambre"] == "nodocean/capteur_chambre"

        # Mesure reçue -> état JSON (correction de température appliquée)
        entry.runtime_data.devices[
            next(k for k, d in entry.runtime_data.devices.items() if d.title == "Capteur chambre")
        ].settings["temperature_offset"] = -0.5
        dongle.inject(0xA5, bytes.fromhex("00 96 7D 0A"), STPH)
        await hass.async_block_till_done()
        state = json.loads(client.last("nodocean/capteur_chambre"))
        assert state["temperature"] == 19.5 and state["humidity"] == 60.0
        assert state["available"] is True and "last_seen" in state and "rssi" in state

        # Appui de bouton -> topic action (non conservé) ; l'entité HA le voit aussi
        dongle.inject(0xF6, bytes.fromhex("70"), CWS)
        await hass.async_block_till_done()
        assert ("nodocean/interrupteur_entree/action", "right_up", False) in client.published
        event_id = er.async_get(hass).async_get_entity_id(
            "event", DOMAIN, "FEF00001_wall_switch"
        )
        assert hass.states.get(event_id).attributes["event_type"] == "right_up"

        # Commande MQTT -> trame radio + entité HA à jour
        switch_id = er.async_get(hass).async_get_entity_id("switch", DOMAIN, "0512AB34_switch")
        dongle.sent.clear()
        client.receive(hass, "nodocean/lampe_salon/set", '{"state": "ON"}')
        await hass.async_block_till_done()
        assert [s for s in dongle.sent if s.rorg == 0xD2][-1].payload.hex(" ") == "01 00 64"
        assert hass.states.get(switch_id).state == "on"
        assert json.loads(client.last("nodocean/lampe_salon"))["state"] == "ON"

        # Texte simple et TOGGLE
        client.receive(hass, "nodocean/lampe_salon/set", "TOGGLE")
        await hass.async_block_till_done()
        assert [s for s in dongle.sent if s.rorg == 0xD2][-1].payload.hex(" ") == "01 00 00"
        assert hass.states.get(switch_id).state == "off"

        # Commande depuis HA -> publiée sur MQTT
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": switch_id}, blocking=True
        )
        await hass.async_block_till_done()
        assert json.loads(client.last("nodocean/lampe_salon"))["state"] == "ON"

        # Commande vers un capteur : ignorée, rien n'est émis
        dongle.sent.clear()
        client.receive(hass, "nodocean/capteur_chambre/set", '{"state": "ON"}')
        client.receive(hass, "nodocean/inconnu/set", "ON")
        client.receive(hass, "nodocean/lampe_salon/availability", "online")
        await hass.async_block_till_done()
        assert not [s for s in dongle.sent if s.rorg == 0xD2]

        # Diagnostics : mot de passe masqué
        from custom_components.nodon_enocean.diagnostics import (  # noqa: PLC0415
            async_get_config_entry_diagnostics,
        )

        diag = await async_get_config_entry_diagnostics(hass, entry)
        assert diag["mqtt"]["connected"] is True
        assert diag["mqtt"]["options"]["mqtt_password"] == "**REDACTED**"

        # Mot de passe laissé vide : l'ancien est conservé ; nommage par ID
        result, _ = await _configure(
            hass,
            entry,
            {**OPTIONS, "mqtt_password": "", "mqtt_topic_name": "id"},
        )
        assert entry.options["mqtt_password"] == "secret"
        assert client.stopped
        client = FakeClient.instances[-1]
        info = json.loads(client.last("nodocean/bridge/info"))
        assert "nodocean/0512AB34" in {d["topic"] for d in info["devices"]}

        # Désactivation : le pont s'arrête
        result, _ = await _configure(hass, entry, {**OPTIONS, "mqtt_enabled": False})
        assert entry.runtime_data.mqtt is None
        assert client.last("nodocean/bridge/state") == "offline"


async def test_mqtt_use_ha_without_mqtt(hass: HomeAssistant, dongle) -> None:
    entry = await _setup_gateway(hass)
    result, _ = await _configure(hass, entry, {**OPTIONS, "mqtt_use_ha": True})
    assert result["errors"] == {"base": "no_ha_mqtt"}
    # Option enregistrée hors assistant (ex. intégration MQTT supprimée) -> alerte
    hass.config_entries.async_update_entry(entry, options={**OPTIONS, "mqtt_use_ha": True})
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"mqtt_config_{entry.entry_id}")
    assert entry.runtime_data.mqtt is None


async def test_mqtt_payload_and_commands(hass: HomeAssistant, dongle) -> None:
    """Conversion des états et commandes pour volet, fil pilote et module 2 canaux."""
    from custom_components.nodon_enocean.catalog import PRODUCTS  # noqa: PLC0415
    from custom_components.nodon_enocean.device import NodOnDevice  # noqa: PLC0415
    from custom_components.nodon_enocean.mqtt_bridge import (  # noqa: PLC0415
        apply_command,
        device_payload,
    )

    entry = await _setup_gateway(hass)
    gateway = entry.runtime_data.gateway

    cover = NodOnDevice(gateway, PRODUCTS["SIN-2-RS-01"], 0x0500AA02, 3, "a", "Volet")
    cover.state["position"] = 0
    assert device_payload(cover) == {"position": 0, "state": "CLOSED"}
    dongle.sent.clear()
    assert await apply_command(cover, {"position": 40}) == []
    assert await apply_command(cover, {"state": "STOP"}) == []
    assert await apply_command(cover, {"state": "UP"}) == ["state"]
    assert len([s for s in dongle.sent if s.rorg == 0xD2]) == 2

    fp = NodOnDevice(gateway, PRODUCTS["SIN-2-FP-01"], 0x0500AA03, 4, "b", "Radiateur")
    await apply_command(fp, {"mode": "eco"})
    assert device_payload(fp)["mode"] == "eco"
    assert await apply_command(fp, {"mode": "turbo"}) == ["mode"]

    duo = NodOnDevice(gateway, PRODUCTS["SIN-2-2-01"], 0x0500AA04, 5, "c", "Éclairage")
    assert await apply_command(duo, {"state_l2": "ON", "state_l3": "ON"}) == ["state_l3"]
    assert device_payload(duo) == {"state_l2": "ON"}
