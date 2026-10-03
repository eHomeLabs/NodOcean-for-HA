"""Réglages des produits (v0.2) : trames, entités de configuration, options HA."""

from __future__ import annotations

import asyncio
import time

from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_get_device_automations

from custom_components.nodon_enocean import eep
from custom_components.nodon_enocean.catalog import PRODUCTS
from custom_components.nodon_enocean.const import DOMAIN

from .fake_dongle import BASE_ID
from .test_integration import _pair, _setup_gateway

SIN21 = 0x0512AB34
SIN22 = 0x0512AB35
MSP = 0x0500AA01
STPH = 0x01A2B3C4
CWS = 0xFEF00001


def _hex(b: bytes) -> str:
    return b.hex(" ").upper()


# --- Trames ----------------------------------------------------------------------


def test_set_local_frames() -> None:
    assert _hex(eep.d201_set_local()) == "82 3E 00 20"  # défauts : jour, précédent
    assert _hex(eep.d201_set_local(led=False)) == "82 3E 00 A0"  # nuit = LED éteinte
    assert _hex(eep.d201_set_local(default_state="on")) == "82 3E 00 10"
    assert _hex(eep.d201_set_local(default_state="off")) == "82 3E 00 00"
    assert _hex(eep.d201_set_local(power_failure=True)) == "82 3E 00 60"
    assert _hex(eep.d201_set_local(local_control=False)) == "82 1E 00 20"


def test_ext_interface_frames() -> None:
    # Exemple NodOn « delay off timer » : 120 s
    assert _hex(eep.d201_set_ext_interface(0, 0, 120)) == "0B 00 00 00 04 B0 00"
    assert _hex(eep.d201_set_ext_interface(1, 10, 0)) == "0B 01 00 64 00 00 00"


def test_measurement_and_msc_frames() -> None:
    cfg = {"delta": 5, "max_interval": 600, "min_interval": 10}
    assert _hex(eep.d201_measurement_config(power=True, **cfg)) == "05 A0 53 00 3C 0A"
    assert (
        _hex(eep.d201_measurement_config(power=False, reset=True, **cfg))
        == "05 C0 51 00 3C 0A"
    )
    assert _hex(eep.msc_set_repeater(0)) == "00 46 08 00 00"
    assert _hex(eep.msc_set_repeater(2)) == "00 46 08 01 02"


def test_manual_links() -> None:
    for product in PRODUCTS.values():
        assert product.manual and product.manual.startswith("https://support.nodon.fr/")


# --- Actionneurs -------------------------------------------------------------------


async def test_actuator_settings(hass: HomeAssistant, dongle) -> None:
    entry = await _setup_gateway(hass)
    entry = await _pair(
        hass,
        entry,
        dongle,
        "SIN-2-1-01",
        lambda: dongle.inject(0xD4, bytes.fromhex("A0 01 46 00 0F 01 D2"), SIN21),
        "Lampe",
    )
    ent = er.async_get(hass)

    def eid(platform: str, key: str) -> str:
        entity_id = ent.async_get_entity_id(platform, DOMAIN, f"0512AB34_{key}")
        assert entity_id, key
        return entity_id

    led, state, auto_off, delay_off = (
        eid("switch", "led"),
        eid("select", "default_state"),
        eid("number", "auto_off_0"),
        eid("number", "delay_off_0"),
    )
    repeater, firmware = eid("select", "repeater"), eid("sensor", "firmware")
    eid("image", "product_image")
    assert ent.async_get_entity_id("switch", DOMAIN, "0512AB34_power_failure") is None

    # Au démarrage : demande du répéteur et du firmware
    await asyncio.sleep(0.6)
    msc = [_hex(s.payload) for s in dongle.sent if s.rorg == 0xD1]
    assert "00 46 09" in msc and "00 46 02" in msc

    dongle.sent.clear()
    assert hass.states.get(led).state == "on"
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": led}, blocking=True
    )
    await hass.services.async_call(
        "select", "select_option", {"entity_id": state, "option": "off"}, blocking=True
    )
    vld = [s for s in dongle.sent if s.rorg == 0xD2]
    assert _hex(vld[0].payload) == "82 3E 00 A0"
    assert _hex(vld[1].payload) == "82 3E 00 80"  # LED éteinte conservée
    assert vld[0].destination == SIN21 and vld[0].sender == BASE_ID + 1
    assert hass.states.get(led).state == "off"

    dongle.sent.clear()
    await hass.services.async_call(
        "number", "set_value", {"entity_id": delay_off, "value": 120}, blocking=True
    )
    await hass.services.async_call(
        "number", "set_value", {"entity_id": auto_off, "value": 10}, blocking=True
    )
    vld = [_hex(s.payload) for s in dongle.sent if s.rorg == 0xD2]
    assert vld == ["0B 00 00 00 04 B0 00", "0B 00 00 64 04 B0 00"]

    dongle.sent.clear()
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": repeater, "option": "level_2"},
        blocking=True,
    )
    assert (
        _hex(dongle.sent[-1].payload) == "00 46 08 01 02"
        and dongle.sent[-1].rorg == 0xD1
    )
    assert hass.states.get(repeater).state == "level_2"

    # Réponses NodOn : répéteur niveau 1, firmware
    dongle.inject(0xD1, bytes.fromhex("46 00 0A 01"), SIN21)
    dongle.inject(0xD1, bytes.fromhex("00 46 03 03 03 00"), SIN21)
    await hass.async_block_till_done()
    assert hass.states.get(repeater).state == "level_1"
    assert hass.states.get(firmware).state == "03.03.00"

    # Lien vers la notice sur la fiche appareil
    dev = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "0512AB34")})
    assert dev.configuration_url == PRODUCTS["SIN-2-1-01"].manual

    # Les réglages survivent à un rechargement (restauration de l'état)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(led).state == "off"
    assert hass.states.get(state).state == "off"
    assert float(hass.states.get(delay_off).state) == 120
    runtime = hass.config_entries.async_get_entry(entry.entry_id).runtime_data
    device = next(iter(runtime.devices.values()))
    assert device.settings["led"] is False and device.settings["default_state"] == "off"


async def test_two_channel_timers(hass: HomeAssistant, dongle) -> None:
    entry = await _setup_gateway(hass)
    await _pair(
        hass,
        entry,
        dongle,
        "SIN-2-2-01",
        lambda: dongle.inject(0xD4, bytes.fromhex("A0 02 46 00 12 01 D2"), SIN22),
        "Éclairage",
    )
    ent = er.async_get(hass)
    ch2 = ent.async_get_entity_id("number", DOMAIN, "0512AB35_auto_off_1")
    assert ch2 and ent.async_get_entity_id("number", DOMAIN, "0512AB35_delay_off_0")
    dongle.sent.clear()
    await hass.services.async_call(
        "number", "set_value", {"entity_id": ch2, "value": 60}, blocking=True
    )
    assert _hex(dongle.sent[-1].payload) == "0B 01 02 58 00 00 00"


async def test_plug_metering(hass: HomeAssistant, dongle) -> None:
    entry = await _setup_gateway(hass)
    await _pair(
        hass,
        entry,
        dongle,
        "MSP-2",
        lambda: dongle.inject(0xD4, bytes.fromhex("A0 01 46 00 0E 01 D2"), MSP),
        "Prise TV",
    )
    await asyncio.sleep(0.8)
    sent = [_hex(s.payload) for s in dongle.sent if s.rorg == 0xD2]
    assert "05 A0 53 00 3C 0A" in sent and "05 80 A1 00 3C 0A" in sent  # rapport auto

    ent = er.async_get(hass)
    for platform, key in (
        ("switch", "local_control"),
        ("switch", "power_failure"),
        ("switch", "led"),
        ("number", "auto_off_0"),
        ("button", "reset_energy"),
    ):
        assert ent.async_get_entity_id(platform, DOMAIN, f"0500AA01_{key}"), key
    assert ent.async_get_entity_id("number", DOMAIN, "0500AA01_delay_off_0") is None

    energy = ent.async_get_entity_id("sensor", DOMAIN, "0500AA01_energy")
    dongle.inject(0xD2, bytes.fromhex("07 20 00 00 03 E8"), MSP)
    await hass.async_block_till_done()
    assert float(hass.states.get(energy).state) == 1.0

    dongle.sent.clear()
    reset = ent.async_get_entity_id("button", DOMAIN, "0500AA01_reset_energy")
    await hass.services.async_call(
        "button", "press", {"entity_id": reset}, blocking=True
    )
    sent = [_hex(s.payload) for s in dongle.sent if s.rorg == 0xD2]
    assert sent[0] == "05 C0 A1 00 3C 0A"
    assert float(hass.states.get(energy).state) == 0.0

    dongle.sent.clear()
    pf = ent.async_get_entity_id("switch", DOMAIN, "0500AA01_power_failure")
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": pf}, blocking=True
    )
    assert _hex(dongle.sent[-1].payload) == "82 3E 00 60"


# --- Capteurs et boutons -----------------------------------------------------------


async def test_sensor_options(hass: HomeAssistant, dongle) -> None:
    entry = await _setup_gateway(hass)
    await _pair(
        hass,
        entry,
        dongle,
        "STPH-2",
        lambda: dongle.inject(0xA5, bytes.fromhex("00 00 00 00"), STPH),
        "Chambre",
    )
    ent = er.async_get(hass)
    temp = ent.async_get_entity_id("sensor", DOMAIN, "01A2B3C4_temperature")
    offset = ent.async_get_entity_id("number", DOMAIN, "01A2B3C4_temperature_offset")
    hum_offset = ent.async_get_entity_id("number", DOMAIN, "01A2B3C4_humidity_offset")
    timeout = ent.async_get_entity_id("number", DOMAIN, "01A2B3C4_timeout")
    assert offset and hum_offset and timeout

    dongle.inject(0xA5, bytes.fromhex("00 96 7D 0A"), STPH)
    await hass.async_block_till_done()
    assert float(hass.states.get(temp).state) == 20.0
    await hass.services.async_call(
        "number", "set_value", {"entity_id": offset, "value": -1.5}, blocking=True
    )
    assert float(hass.states.get(temp).state) == 18.5

    # Délai d'absence : capteur muet depuis 2 h, délai 60 min -> indisponible
    await hass.services.async_call(
        "number", "set_value", {"entity_id": timeout, "value": 60}, blocking=True
    )
    device = next(iter(entry.runtime_data.devices.values()))
    device.last_seen = time.monotonic() - 7200
    device.notify({"_availability"})
    await hass.async_block_till_done()
    assert hass.states.get(temp).state == "unavailable"
    assert hass.states.get(timeout).state == "60"  # le réglage reste modifiable
    dongle.inject(0xA5, bytes.fromhex("00 96 7D 0A"), STPH)
    await hass.async_block_till_done()
    assert float(hass.states.get(temp).state) == 18.5


async def test_wall_switch_triggers(hass: HomeAssistant, dongle) -> None:
    entry = await _setup_gateway(hass)
    await _pair(
        hass,
        entry,
        dongle,
        "CWS-2-1",
        lambda: dongle.inject(0xF6, bytes.fromhex("30"), CWS),
        "Interrupteur",
    )
    dev = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "FEF00001")})
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, dev.id
    )
    types = {t["type"] for t in triggers if t["domain"] == DOMAIN}
    assert "left_up" in types and "up" not in types

    calls: list = []
    hass.bus.async_listen(f"{DOMAIN}_button", lambda e: calls.append(e.data["type"]))
    dongle.inject(0xF6, bytes.fromhex("70"), CWS)
    await hass.async_block_till_done()
    assert calls == ["right_up"]

    # Façade 2 boutons : haut / bas uniquement
    ent = er.async_get(hass)
    mode = ent.async_get_entity_id("select", DOMAIN, "FEF00001_buttons")
    await hass.services.async_call(
        "select", "select_option", {"entity_id": mode, "option": "2"}, blocking=True
    )
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, dev.id
    )
    assert {t["type"] for t in triggers if t["domain"] == DOMAIN} == {
        "up",
        "down",
        "release",
    }
    dongle.inject(0xF6, bytes.fromhex("50"), CWS)
    await hass.async_block_till_done()
    assert calls[-1] == "down"

    # Une automatisation sur le déclencheur d'appareil se déclenche
    fired: list = []
    hass.bus.async_listen("test_fired", lambda e: fired.append(1))
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "device",
                    "domain": DOMAIN,
                    "device_id": dev.id,
                    "type": "up",
                },
                "action": {"event": "test_fired"},
            }
        },
    )
    dongle.inject(0xF6, bytes.fromhex("30"), CWS)
    await hass.async_block_till_done()
    assert fired == [1]


# --- v0.3 : nouveaux produits, aide ------------------------------------------------

CRC = 0xFEF00002
CFS = 0xFEF00003
CCS = 0xFEF00004
PIR = 0x0199AA01


def test_new_product_decoders() -> None:
    from custom_components.nodon_enocean.esp3 import RadioTelegram  # noqa: PLC0415

    def rps(b: int) -> RadioTelegram:
        return RadioTelegram(0xF6, bytes([b]), 1, 0x30)

    # Soft Remote : 50 = haut gauche, 10 = haut droite, 35 = haut gauche + bas droite
    remote = eep.SOFT_REMOTE_NAMES
    assert eep.decode_f60201(rps(0x50), remote) == {"event": "left_up"}
    assert eep.decode_f60201(rps(0x10), remote) == {"event": "right_up"}
    assert eep.decode_f60201(rps(0x35), remote) == {"event": "left_up_right_down"}
    assert eep.decode_single_button(rps(0x30)) == {"event": "press"}
    assert eep.decode_f60401(rps(0x30)) == {"card": True}
    assert eep.decode_f60401(rps(0x00)) == {"card": False}
    # PIR : C8 = 4,0 V ; 69 00 -> 420 lx ; 88 = mouvement
    pir = RadioTelegram(0xA5, bytes.fromhex("C8 69 00 88"), 1, 0)
    assert eep.decode_a50703(pir) == {"motion": True, "voltage": 4.0, "illuminance": 420}


async def test_new_products(hass: HomeAssistant, dongle) -> None:
    entry = await _setup_gateway(hass)
    entry = await _pair(
        hass, entry, dongle, "CRC-2", lambda: dongle.inject(0xF6, bytes.fromhex("50"), CRC), "Télécommande"
    )
    entry = await _pair(
        hass, entry, dongle, "CFS-2", lambda: dongle.inject(0xF6, bytes.fromhex("30"), CFS), "Sol"
    )
    entry = await _pair(
        hass, entry, dongle, "CCS-2", lambda: dongle.inject(0xF6, bytes.fromhex("30"), CCS), "Carte"
    )
    entry = await _pair(
        hass,
        entry,
        dongle,
        "PIR-2",
        lambda: dongle.inject(0xA5, bytes.fromhex("1C 18 46 80"), PIR),
        "Couloir",
    )
    ent = er.async_get(hass)
    remote = ent.async_get_entity_id("event", DOMAIN, "FEF00002_soft_remote")
    floor = ent.async_get_entity_id("event", DOMAIN, "FEF00003_floor_switch")
    card = ent.async_get_entity_id("binary_sensor", DOMAIN, "FEF00004_card")
    motion = ent.async_get_entity_id("binary_sensor", DOMAIN, "0199AA01_motion")
    lux = ent.async_get_entity_id("sensor", DOMAIN, "0199AA01_illuminance")
    assert all([remote, floor, card, motion, lux])

    dongle.inject(0xF6, bytes.fromhex("70"), CRC)
    dongle.inject(0xF6, bytes.fromhex("30"), CFS)
    dongle.inject(0xF6, bytes.fromhex("00"), CCS)
    dongle.inject(0xA5, bytes.fromhex("C8 69 00 88"), PIR)
    await hass.async_block_till_done()
    assert hass.states.get(remote).attributes["event_type"] == "left_down"
    assert hass.states.get(floor).attributes["event_type"] == "press"
    assert hass.states.get(card).state == "off"
    assert hass.states.get(motion).state == "on"
    assert float(hass.states.get(lux).state) == 420

    dev = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "FEF00003")})
    triggers = await async_get_device_automations(hass, DeviceAutomationType.TRIGGER, dev.id)
    assert {t["type"] for t in triggers if t["domain"] == DOMAIN} == {"press", "release"}

    # Bouton Aide : notification avec la notice et le support NodOn
    help_btn = ent.async_get_entity_id("button", DOMAIN, "0199AA01_help")
    await hass.services.async_call("button", "press", {"entity_id": help_btn}, blocking=True)
    from homeassistant.components import persistent_notification  # noqa: PLC0415

    notes = persistent_notification._async_get_or_create_notifications(hass)
    note = notes["nodon_help_0199AA01"]
    assert PRODUCTS["PIR-2"].manual in note["message"]
    assert "support.nodon.fr" in note["message"]


# --- v0.4 : doublons, diagnostics, reconfiguration, réparations --------------------


async def test_duplicates_ignored(hass: HomeAssistant, dongle) -> None:
    entry = await _setup_gateway(hass)
    await _pair(
        hass, entry, dongle, "CWS-2-1", lambda: dongle.inject(0xF6, bytes.fromhex("30"), CWS), "Inter"
    )
    calls: list = []
    hass.bus.async_listen(f"{DOMAIN}_button", lambda e: calls.append(e.data["type"]))
    # Original + copie répétée par un module (compteur de répétitions = 1)
    dongle.inject(0xF6, bytes.fromhex("70"), CWS)
    dongle.inject(0xF6, bytes.fromhex("70"), CWS, status=0x31)
    await hass.async_block_till_done()
    assert calls == ["right_up"]
    # Deux vrais appuis rapides (non répétés) : tous deux pris en compte
    dongle.inject(0xF6, bytes.fromhex("00"), CWS)
    dongle.inject(0xF6, bytes.fromhex("70"), CWS)
    await hass.async_block_till_done()
    assert calls.count("right_up") == 2
    assert entry.runtime_data.gateway.duplicates == 1


async def test_diagnostics(hass: HomeAssistant, dongle) -> None:
    from custom_components.nodon_enocean.diagnostics import (  # noqa: PLC0415
        async_get_config_entry_diagnostics,
        async_get_device_diagnostics,
    )

    entry = await _setup_gateway(hass)
    entry = await _pair(
        hass,
        entry,
        dongle,
        "SIN-2-1-01",
        lambda: dongle.inject(0xD4, bytes.fromhex("A0 01 46 00 0F 01 D2"), SIN21),
        "Lampe",
    )
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["gateway"]["base_id"] == "FF8A2C00"
    assert diag["products"][0]["model"] == "SIN-2-1-01"
    assert any(t["dir"] == "tx" and t["rorg"] == "D4" for t in diag["last_telegrams"])
    dev = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "0512AB34")})
    ddiag = await async_get_device_diagnostics(hass, entry, dev)
    assert ddiag["product"]["enocean_id"] == "0512AB34"
    assert all("0512AB34" in (t["sender"], t["destination"]) for t in ddiag["last_telegrams"])


async def test_reconfigure_port(hass: HomeAssistant, dongle) -> None:
    from homeassistant.data_entry_flow import FlowResultType  # noqa: PLC0415

    entry = await _setup_gateway(hass)
    entry = await _pair(
        hass, entry, dongle, "STPH-2", lambda: dongle.inject(0xA5, bytes(4), STPH), "Chambre"
    )
    # Même clé, nouveau chemin : produits conservés
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
    )
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "/dev/serial/by-id/usb-EnOcean_USB_300"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry.data["device"] == "/dev/serial/by-id/usb-EnOcean_USB_300"
    assert len(entry.subentries) == 1

    # Autre clé : avertissement puis adoption
    dongle.base_id = 0xFFAA0000
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "/dev/ttyUSB1"}
    )
    assert result["step_id"] == "reconfigure_new_key"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry.unique_id == "FFAA0000" and entry.title == "Clé EnOcean FFAA0000"
    assert len(entry.subentries) == 1


async def test_repair_issue_when_stick_missing(hass: HomeAssistant) -> None:
    from unittest.mock import patch  # noqa: PLC0415

    from homeassistant.helpers import issue_registry as ir  # noqa: PLC0415
    from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: PLC0415

    from custom_components.nodon_enocean.gateway import (  # noqa: PLC0415
        Gateway,
        GatewayOpenError,
    )

    entry = MockConfigEntry(domain=DOMAIN, unique_id="FF8A2C00", data={"device": "/dev/absent"})
    entry.add_to_hass(hass)
    with patch.object(Gateway, "connect", side_effect=GatewayOpenError("No such file")):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"gateway_unavailable_{entry.entry_id}")
    assert issue is not None and issue.translation_key == "gateway_unavailable"
    assert issue.translation_placeholders["port"] == "/dev/absent"


def test_translations_complete() -> None:
    import json  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    base = Path(__file__).parent.parent / "custom_components" / "nodon_enocean"

    def keys(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield from keys(v, f"{prefix}/{k}")
        else:
            yield prefix

    ref = set(keys(json.loads((base / "strings.json").read_text())))
    for lang in ("en", "fr", "de"):
        data = json.loads((base / "translations" / f"{lang}.json").read_text())
        assert set(keys(data)) == ref, lang
    for product in PRODUCTS.values():
        assert product.pairing("de") != product.pairing_en
