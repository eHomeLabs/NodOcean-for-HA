"""Multibrand receive-only flows, identity retention and feature isolation."""

import asyncio

import pytest
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.nodon_enocean.catalog import (
    ADD_MANUFACTURERS,
    GENERIC_PRODUCTS,
    PRODUCTS,
)
from custom_components.nodon_enocean.const import DOMAIN
from custom_components.nodon_enocean.device_trigger import async_get_triggers

from .test_integration import _pair, _setup_gateway


def test_catalogue_is_bounded():
    assert ADD_MANUFACTURERS == ("NodOn", "Generic")
    nodon = {p.eep for p in PRODUCTS.values() if p.manufacturer == "NodOn"}
    # One generic profile per EEP already used by a NodOn product, nothing more.
    assert set(GENERIC_PRODUCTS) == nodon
    assert PRODUCTS["SIN-2-1-01"].manufacturer == "NodOn"
    assert PRODUCTS["SIN-2-1-01"].model == "SIN-2-1-01"
    for code, p in GENERIC_PRODUCTS.items():
        base = PRODUCTS[p.base_model]
        assert base.manufacturer == "NodOn" and base.eep == code
        assert p.teach_in == base.teach_in and p.channels == base.channels
        assert p.metering == base.metering and p.image is None


@pytest.mark.parametrize(
    ("manufacturer", "selection", "rorg", "teach", "data", "domain", "key", "expected"),
    [
        (
            "Generic",
            {"eep": "F6-02-01"},
            0xF6,
            "30",
            "00",
            "event",
            "wall_switch",
            "release",
        ),
        (
            "Generic",
            {"eep": "D5-00-01"},
            0xD5,
            "00",
            "08",
            "binary_sensor",
            "opening",
            "on",
        ),
        (
            "Generic",
            {"eep": "A5-02-05"},
            0xA5,
            "00 00 00 00",
            "00 00 80 08",
            "sensor",
            "temperature",
            None,
        ),
        (
            "Generic",
            {"eep": "A5-04-01"},
            0xA5,
            "00 00 00 00",
            "00 7D 7D 08",
            "sensor",
            "humidity",
            None,
        ),
    ],
)
async def test_receive_flow(
    hass, dongle, manufacturer, selection, rorg, teach, data, domain, key, expected
):
    entry = await _setup_gateway(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"), context={"source": "user"}
    )
    product = (
        PRODUCTS[selection["model"]]
        if "model" in selection
        else GENERIC_PRODUCTS[selection["eep"]]
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"manufacturer": manufacturer.lower()}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"model": product.model}
    )
    assert result["step_id"] == "instructions"
    assert result["description_placeholders"]["support"]
    assert result["description_placeholders"]["image"] == ""
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    await asyncio.sleep(0)
    dongle.inject(rorg, bytes.fromhex(teach), 0x01020304)
    await hass.async_block_till_done()
    result = await hass.config_entries.subentries.async_configure(result["flow_id"])
    assert result["step_id"] == "confirm"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Test multimarque"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(domain, DOMAIN, f"01020304_{key}")
    assert entity_id
    record = registry.async_get(entity_id)
    dev = dr.async_get(hass).async_get(record.device_id)
    assert dev.manufacturer == manufacturer
    assert not any(
        "help" in e.unique_id or e.domain == "image"
        for e in registry.entities.values()
        if e.device_id == dev.id
    )
    fake = entry.runtime_data.gateway._transport
    fake.inject(rorg, bytes.fromhex(data), 0x01020304)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    if domain == "event":
        assert state.attributes["event_type"] == expected
        assert await async_get_triggers(hass, dev.id)
    elif expected:
        assert state.state == expected
    else:
        assert state.state not in ("unknown", "unavailable")
    assert not fake.sent, "Receive-only products must not send manufacturer commands"
    # Restart: model and entity registry identity are retained.
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(entity_id).id == record.id
    assert registry.async_get(entity_id).device_id == dev.id


async def test_legacy_identity_survives_reload(hass, dongle):
    entry = await _setup_gateway(hass)
    entry = await _pair(
        hass,
        entry,
        dongle,
        "SIN-2-1-01",
        lambda: dongle.inject(0xD4, bytes.fromhex("A0 01 46 00 0F 01 D2"), 0x0512AB34),
        "Legacy relay",
    )
    registry = er.async_get(hass)
    before = {
        e.unique_id: (e.entity_id, e.device_id) for e in registry.entities.values()
    }
    sub = next(iter(entry.subentries.values()))
    saved = dict(sub.data)
    assert saved["sender_offset"] == 1
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert dict(next(iter(entry.subentries.values())).data) == saved
    assert before == {
        e.unique_id: (e.entity_id, e.device_id) for e in registry.entities.values()
    }


def test_generic_pairing_rejects_wrong_profile():
    from custom_components.nodon_enocean.esp3 import RadioTelegram
    from custom_components.nodon_enocean.pairing import match_teach_in

    p = GENERIC_PRODUCTS["A5-02-05"]
    # Advertised A5-04-01 teach-in must not be accepted as A5-02-05.
    telegram = RadioTelegram(
        rorg=0xA5, payload=bytes.fromhex("10 08 46 80"), sender=0x01020304
    )
    assert not match_teach_in(p, telegram)[0]
    assert not match_teach_in(
        GENERIC_PRODUCTS["F6-02-01"],
        RadioTelegram(rorg=0xD5, payload=b"\x00", sender=0x01020304),
    )[0]


async def test_two_step_form(hass, dongle):
    entry = await _setup_gateway(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"), context={"source": "user"}
    )
    assert result["step_id"] == "user"
    assert result["description_placeholders"] == {"gallery": ""}
    fields = {key.schema: value for key, value in result["data_schema"].schema.items()}
    assert set(fields) == {"manufacturer"}
    assert fields["manufacturer"].config["options"] == ["nodon", "generic"]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"manufacturer": "nodon"}
    )
    assert result["step_id"] == "product"
    assert "produits-nodon.png" in result["description_placeholders"]["gallery"]
    fields = {key.schema: value for key, value in result["data_schema"].schema.items()}
    models = [opt["value"] for opt in fields["model"].config["options"]]
    assert models and all(PRODUCTS[m].manufacturer == "NodOn" for m in models)
    # A product of another manufacturer is not in the list: refused.
    with pytest.raises(InvalidData):
        await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"model": "EEP-D5-00-01"}
        )
    hass.config_entries.subentries.async_abort(result["flow_id"])

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"), context={"source": "user"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"manufacturer": "generic"}
    )
    assert result["description_placeholders"]["gallery"] == ""
    fields = {key.schema: value for key, value in result["data_schema"].schema.items()}
    options = fields["model"].config["options"]
    assert {opt["value"] for opt in options} == {p.model for p in GENERIC_PRODUCTS.values()}
    assert all(opt["label"].startswith(PRODUCTS[opt["value"]].eep) for opt in options)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"model": "EEP-D5-00-01"}
    )
    assert result["step_id"] == "instructions"
    hass.config_entries.subentries.async_abort(result["flow_id"])
    assert not entry.subentries


async def test_generic_actuator(hass, dongle):
    """Generic D2-01-0F: relay switch, no NodOn-only entities."""
    entry = await _setup_gateway(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"), context={"source": "user"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"manufacturer": "generic"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"model": "EEP-D2-01-0F"}
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    await asyncio.sleep(0)
    # UTE teach-in request from another manufacturer (0x00D).
    dongle.inject(0xD4, bytes.fromhex("A0 01 0D 00 0F 01 D2"), 0x01020305)
    await hass.async_block_till_done()
    result = await hass.config_entries.subentries.async_configure(result["flow_id"])
    assert result["step_id"] == "confirm", result
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Relais générique"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    uids = {e.unique_id for e in registry.entities.values()}
    assert any(u.startswith("01020305_") and u.endswith("_switch") or u == "01020305_switch" for u in uids), uids
    for key in ("help", "repeater", "firmware", "links", "recom", "led", "default_state"):
        assert not any(u.startswith("01020305") and key in u for u in uids), (key, uids)
