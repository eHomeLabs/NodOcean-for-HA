"""Tests de bout en bout : clé, ajout guidé des produits, entités, commandes."""

from __future__ import annotations

import asyncio

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.nodon_enocean.const import DOMAIN

from .fake_dongle import BASE_ID

SIN21 = 0x0512AB34
STPH = 0x01A2B3C4
CWS = 0xFEF00001
MSP = 0x0500AA01
RS = 0x0500AA02


async def _setup_gateway(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "/dev/ttyUSB0"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Clé EnOcean FF8A2C00"
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is ConfigEntryState.LOADED
    return entry


async def _pair(hass, entry, dongle, model, inject, name, area_id=None, new_area=None):
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"), context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"model": model}
    )
    assert result["step_id"] == "instructions"
    assert model in result["description_placeholders"]["model"]
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await asyncio.sleep(0)
    inject()
    await hass.async_block_till_done()
    result = await hass.config_entries.subentries.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM, result
    assert result["step_id"] == "confirm"
    user_input = {"name": name}
    if area_id:
        user_input["area_id"] = area_id
    if new_area:
        user_input["new_area"] = new_area
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], user_input)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return hass.config_entries.async_get_entry(entry.entry_id)


async def test_full_flow(hass: HomeAssistant, dongle) -> None:
    entry = await _setup_gateway(hass)
    from homeassistant.helpers import area_registry as ar  # noqa: PLC0415

    garage = ar.async_get(hass).async_get_or_create("Garage")

    # 1) Actionneur : UTE bidirectionnel -> réponse automatique
    entry = await _pair(
        hass,
        entry,
        dongle,
        "SIN-2-1-01",
        lambda: dongle.inject(0xD4, bytes.fromhex("A0 01 46 00 0F 01 D2"), SIN21),
        "Lampe salon",
        garage.id,
    )
    ute_resp = [s for s in dongle.sent if s.rorg == 0xD4]
    assert ute_resp, "aucune réponse UTE envoyée"
    assert ute_resp[0].payload.hex(" ").upper() == "91 01 46 00 0F 01 D2"
    assert ute_resp[0].destination == SIN21
    assert ute_resp[0].sender == BASE_ID + 1

    # 2) Capteur 4BS
    entry = await _pair(
        hass,
        entry,
        dongle,
        "STPH-2",
        lambda: dongle.inject(0xA5, bytes.fromhex("00 00 00 00"), STPH),
        "Chambre",
    )
    # 3) Interrupteur RPS
    entry = await _pair(
        hass,
        entry,
        dongle,
        "CWS-2-1",
        lambda: dongle.inject(0xF6, bytes.fromhex("30"), CWS),
        "Interrupteur entrée",
        new_area="Entrée",
    )
    # 4) Prise avec mesure : doit obtenir un 2e identifiant d'émission
    entry = await _pair(
        hass,
        entry,
        dongle,
        "MSP-2",
        lambda: dongle.inject(0xD4, bytes.fromhex("A0 01 46 00 0E 01 D2"), MSP),
        "Prise TV",
    )
    assert [s for s in dongle.sent if s.rorg == 0xD4][-1].sender == BASE_ID + 2
    # 5) Volet
    entry = await _pair(
        hass,
        entry,
        dongle,
        "SIN-2-RS-01",
        lambda: dongle.inject(0xD4, bytes.fromhex("A0 01 46 00 00 05 D2"), RS),
        "Volet cuisine",
    )

    assert len(entry.subentries) == 5
    dev_reg = dr.async_get(hass)
    dev = dev_reg.async_get_device(identifiers={(DOMAIN, "0512AB34")})
    assert dev and dev.manufacturer == "NodOn" and dev.model_id == "SIN-2-1-01"
    assert dev.area_id == garage.id
    other = dev_reg.async_get_device(identifiers={(DOMAIN, "01A2B3C4")})
    assert other.area_id is None
    entree = ar.async_get(hass).async_get_area_by_name("Entrée")
    assert (
        entree and dev_reg.async_get_device(identifiers={(DOMAIN, "FEF00001")}).area_id == entree.id
    )

    ent_reg = er.async_get(hass)
    switch_id = ent_reg.async_get_entity_id("switch", DOMAIN, "0512AB34_switch")
    temp_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "01A2B3C4_temperature")
    hum_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "01A2B3C4_humidity")
    event_id = ent_reg.async_get_entity_id("event", DOMAIN, "FEF00001_wall_switch")
    power_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "0500AA01_power")
    energy_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "0500AA01_energy")
    cover_id = ent_reg.async_get_entity_id("cover", DOMAIN, "0500AA02_cover")
    assert all([switch_id, temp_id, hum_id, event_id, power_id, energy_id, cover_id])

    # Commande ON -> trame VLD adressée, depuis l'ID d'émission du module
    dongle.sent.clear()
    await hass.services.async_call("switch", "turn_on", {"entity_id": switch_id}, blocking=True)
    vld = [s for s in dongle.sent if s.rorg == 0xD2]
    assert vld[-1].payload.hex(" ") == "01 00 64"
    assert vld[-1].destination == SIN21 and vld[-1].sender == BASE_ID + 1

    # Retour d'état OFF du module
    dongle.inject(0xD2, bytes.fromhex("04 60 80"), SIN21)
    await hass.async_block_till_done()
    assert hass.states.get(switch_id).state == "off"

    # Mesures température / humidité
    dongle.inject(0xA5, bytes.fromhex("00 96 7D 0A"), STPH)
    await hass.async_block_till_done()
    assert float(hass.states.get(temp_id).state) == 20.0
    assert float(hass.states.get(hum_id).state) == 60.0

    # Appui interrupteur
    dongle.inject(0xF6, bytes.fromhex("70"), CWS)
    await hass.async_block_till_done()
    assert hass.states.get(event_id).attributes["event_type"] == "right_up"

    # Mesure de puissance / énergie de la Micro Smart Plug
    dongle.inject(0xD2, bytes.fromhex("07 60 00 00 00 2A"), MSP)
    dongle.inject(0xD2, bytes.fromhex("07 20 00 00 03 E8"), MSP)
    await hass.async_block_till_done()
    assert float(hass.states.get(power_id).state) == 42.0
    assert float(hass.states.get(energy_id).state) == 1.0

    # Volet : fermeture puis retour de position
    dongle.sent.clear()
    await hass.services.async_call("cover", "close_cover", {"entity_id": cover_id}, blocking=True)
    assert [s for s in dongle.sent if s.rorg == 0xD2][-1].payload.hex(" ") == "64 00 00 01"
    dongle.inject(0xD2, bytes.fromhex("64 00 00 04"), RS)
    await hass.async_block_till_done()
    assert hass.states.get(cover_id).state == "closed"

    # Un appareil déjà connu ne peut pas être ré-appairé
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"), context={"source": "user"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"model": "STPH-2"}
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    await asyncio.sleep(0)
    dongle.inject(0xA5, bytes.fromhex("00 00 00 00"), STPH)
    await asyncio.sleep(0.05)
    flow = hass.config_entries.subentries.async_get(result["flow_id"])
    assert flow["step_id"] == "pairing"  # toujours en attente : ignoré
    hass.config_entries.subentries.async_abort(result["flow_id"])

    # Déchargement propre
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert dongle.closed


async def test_manual_entry_after_timeout(hass: HomeAssistant, dongle, monkeypatch) -> None:
    monkeypatch.setattr("custom_components.nodon_enocean.config_flow.PAIRING_TIMEOUT", 0.05)
    entry = await _setup_gateway(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"), context={"source": "user"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"model": "SDO-2"}
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    await asyncio.sleep(0.1)
    await hass.async_block_till_done()
    result = await hass.config_entries.subentries.async_configure(result["flow_id"])
    assert result["step_id"] == "timeout"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"action": "manual"}
    )
    assert result["step_id"] == "manual"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"device_id": "zz"}
    )
    assert result["errors"] == {"device_id": "invalid_id"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"device_id": "05:00:00:99"}
    )
    assert result["step_id"] == "confirm"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Porte d'entrée"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    ent_reg = er.async_get(hass)
    opening = ent_reg.async_get_entity_id("binary_sensor", DOMAIN, "05000099_opening")
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    gw = entry.runtime_data.gateway
    from .fake_dongle import FakeDongle  # noqa: PLC0415

    fake: FakeDongle = gw._transport
    fake.inject(0xD5, bytes.fromhex("08"), 0x05000099)
    await hass.async_block_till_done()
    assert hass.states.get(opening).state == "on"
