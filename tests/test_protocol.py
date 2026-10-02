"""Tests du protocole ESP3 et des décodeurs EEP (trames issues des docs NodOn)."""

from custom_components.nodon_enocean import eep
from custom_components.nodon_enocean.catalog import PRODUCTS
from custom_components.nodon_enocean.esp3 import (
    ESP3Parser,
    Packet,
    RadioTelegram,
    build_radio,
    build_ute_response,
    crc8,
    parse_radio,
    parse_ute,
    str_to_id,
)
from custom_components.nodon_enocean.pairing import match_teach_in

SENDER = 0x0512AB34


def t(rorg: int, payload: str, status: int = 0) -> RadioTelegram:
    return RadioTelegram(rorg=rorg, payload=bytes.fromhex(payload), sender=SENDER, status=status)


def test_crc8_known_vector() -> None:
    # En-tête de CO_RD_VERSION : 55 00 01 00 05 70 ...
    assert crc8(bytes([0x00, 0x01, 0x00, 0x05])) == 0x70


def test_packet_roundtrip_with_noise() -> None:
    pkt = build_radio(0xD2, bytes([0x01, 0x00, 0x64]), 0xFF8A2C01, SENDER)
    stream = b"\x00\x55\x12" + pkt.encode() + pkt.encode()[:5]
    parser = ESP3Parser()
    packets = parser.feed(stream)
    assert len(packets) == 1
    radio = parse_radio(packets[0])
    assert radio.rorg == 0xD2
    assert radio.payload == bytes([0x01, 0x00, 0x64])
    assert radio.sender == 0xFF8A2C01
    assert radio.destination == SENDER
    # La suite du paquet tronqué arrive ensuite
    assert len(parser.feed(pkt.encode()[5:])) == 1


def test_adt_unwrap() -> None:
    data = (
        bytes([0xA6, 0xD2, 0x04, 0x60, 0xE4])
        + (0xFF8A2C01).to_bytes(4, "big")
        + SENDER.to_bytes(4, "big")
        + b"\x00"
    )
    radio = parse_radio(Packet(0x01, data))
    assert radio.rorg == 0xD2
    assert radio.payload == bytes([0x04, 0x60, 0xE4])
    assert radio.destination == 0xFF8A2C01
    assert radio.sender == SENDER


def test_str_to_id() -> None:
    assert str_to_id("05:12:ab:34") == SENDER
    assert str_to_id("0x0512AB34") == SENDER


# --- UTE ---------------------------------------------------------------------


def test_ute_sin_2_1_01() -> None:
    req = parse_ute(t(0xD4, "A0 01 46 00 0F 01 D2"))
    assert req.bidirectional and req.response_expected
    assert req.manufacturer == 0x046
    assert req.eep == "D2-01-0F"
    # Réponse attendue d'après la Quick User Guide NodOn
    assert build_ute_response(req).hex(" ").upper() == "91 01 46 00 0F 01 D2"


def test_ute_soft_button_unidirectional() -> None:
    req = parse_ute(t(0xD4, "60 01 46 00 0A 03 D2"))
    assert not req.bidirectional and not req.response_expected
    assert req.eep == "D2-03-0A"


def test_match_teach_in_per_product() -> None:
    ute = {
        "SIN-2-1-01": "A0 01 46 00 0F 01 D2",
        "SIN-2-2-01": "A0 02 46 00 12 01 D2",
        "SIN-2-FP-01": "A0 01 46 00 0C 01 D2",
        "SIN-2-RS-01": "A0 01 46 00 00 05 D2",
        "ASP-2": "A0 01 46 00 0A 01 D2",
        "MSP-2": "A0 01 46 00 0E 01 D2",
        "TSB-2": "60 01 46 00 0A 03 D2",
    }
    for model, frame in ute.items():
        ok, req = match_teach_in(PRODUCTS[model], t(0xD4, frame))
        assert ok and req is not None, model
        # Un autre produit ne doit pas accepter cette trame
        other = "ASP-2" if model != "ASP-2" else "MSP-2"
        assert not match_teach_in(PRODUCTS[other], t(0xD4, frame))[0]

    assert match_teach_in(PRODUCTS["SDO-2"], t(0xD5, "00"))[0]
    assert not match_teach_in(PRODUCTS["SDO-2"], t(0xD5, "09"))[0]
    assert match_teach_in(PRODUCTS["SWO-2"], t(0xD5, "01"))[0]
    assert match_teach_in(PRODUCTS["STP-2"], t(0xA5, "00 00 7D 00"))[0]
    assert not match_teach_in(PRODUCTS["STP-2"], t(0xA5, "00 00 7D 08"))[0]
    assert match_teach_in(PRODUCTS["CWS-2-1"], t(0xF6, "30", 0x30))[0]
    assert not match_teach_in(PRODUCTS["CWS-2-1"], t(0xF6, "00", 0x20))[0]


def test_4bs_teach_in_variant2_filters_eep() -> None:
    # A5-04-01, fabricant 0x046, LRN type = 1
    func, type_, manu = 0x04, 0x01, 0x046
    db3 = (func << 2) | (type_ >> 5)
    db2 = ((type_ & 0x1F) << 3) | (manu >> 8)
    frame = bytes([db3, db2, manu & 0xFF, 0x80]).hex()
    assert match_teach_in(PRODUCTS["STPH-2"], t(0xA5, frame))[0]
    assert not match_teach_in(PRODUCTS["STP-2"], t(0xA5, frame))[0]


# --- D2-01 -------------------------------------------------------------------


def test_d201_commands_match_nodon_docs() -> None:
    assert eep.d201_set_output(0, True).hex(" ") == "01 00 64"
    assert eep.d201_set_output(0, False).hex(" ") == "01 00 00"
    assert eep.d201_set_output(1, True).hex(" ") == "01 01 64"
    assert eep.d201_measurement_query(power=True).hex(" ") == "06 20"
    assert eep.d201_measurement_query(power=False).hex(" ") == "06 00"
    assert eep.d201_pilot_wire_set(2).hex(" ") == "08 02"


def test_d201_status() -> None:
    assert eep.decode_d201(t(0xD2, "04 60 E4")) == {"output_0": True}
    assert eep.decode_d201(t(0xD2, "04 60 80")) == {"output_0": False}
    # MSP-2 répond avec 0x61 : canal ignoré pour un produit 1 canal
    assert eep.decode_d201(t(0xD2, "04 61 E4")) == {"output_0": True}
    # SIN-2-2-01 : canal 2
    assert eep.decode_d201(t(0xD2, "04 61 E4"), channels=2) == {"output_1": True}
    assert eep.decode_d201(t(0xD2, "04 60 80"), channels=2) == {"output_0": False}


def test_d201_measurement() -> None:
    # Puissance : unité W (3), 1234 W
    assert eep.decode_d201(t(0xD2, "07 60 00 00 04 D2")) == {"power": 1234.0}
    # Énergie : unité Wh (1), 15500 Wh -> 15.5 kWh
    assert eep.decode_d201(t(0xD2, "07 20 00 00 3C 8C")) == {"energy": 15.5}


def test_d201_pilot_wire_status() -> None:
    assert eep.decode_d201(t(0xD2, "0A 03")) == {"pilot_wire_mode": 3}


# --- D2-05-00 ----------------------------------------------------------------


def test_d205() -> None:
    # HA 100 (ouvert) -> appareil 0 % (« Monter : 00 00 00 01 »)
    assert eep.d205_go_to(100).hex(" ") == "00 00 00 01"
    assert eep.d205_go_to(0).hex(" ") == "64 00 00 01"
    assert eep.d205_go_to(50).hex(" ") == "32 00 00 01"
    assert eep.d205_stop().hex() == "02"
    assert eep.decode_d205(t(0xD2, "00 00 00 04")) == {"position": 100}
    assert eep.decode_d205(t(0xD2, "64 00 00 04")) == {"position": 0}
    assert eep.decode_d205(t(0xD2, "7F 00 00 04")) == {"position": None}


# --- Capteurs ----------------------------------------------------------------


def test_d50001() -> None:
    assert eep.decode_d50001(t(0xD5, "09")) == {"opening": False}  # fermé
    assert eep.decode_d50001(t(0xD5, "08")) == {"opening": True}  # ouvert
    assert eep.decode_d50001(t(0xD5, "00")) is None  # teach-in


def test_a50205() -> None:
    assert eep.decode_a50205(t(0xA5, "00 00 FF 08")) == {"temperature": 0.0}
    assert eep.decode_a50205(t(0xA5, "00 00 00 08")) == {"temperature": 40.0}
    assert eep.decode_a50205(t(0xA5, "00 00 7D 08")) == {"temperature": 20.4}


def test_a50401() -> None:
    # Exemples NodOn : HH=0x96 -> 60 %, TT=0x7D -> 20 °C
    assert eep.decode_a50401(t(0xA5, "00 96 7D 0A")) == {"humidity": 60.0, "temperature": 20.0}


def test_f60201() -> None:
    cases = {
        "30": "left_up",
        "10": "left_down",
        "70": "right_up",
        "50": "right_down",
        "35": "left_up_right_down",
        "17": "left_down_right_up",
        "37": "left_up_right_up",
        "15": "left_down_right_down",
    }
    for raw, name in cases.items():
        assert eep.decode_f60201(t(0xF6, raw, 0x30)) == {"event": name}, raw
    assert eep.decode_f60201(t(0xF6, "00", 0x20)) == {"event": "release"}


def test_d2030a() -> None:
    assert eep.decode_d2030a(t(0xD2, "64 01")) == {"battery": 100, "event": "single"}
    assert eep.decode_d2030a(t(0xD2, "50 02")) == {"battery": 80, "event": "double"}
    assert eep.decode_d2030a(t(0xD2, "0A 04")) == {"battery": 10, "event": "long_release"}


def test_catalog_complete() -> None:
    assert set(PRODUCTS) == {
        "SIN-2-1-01",
        "SIN-2-FP-01",
        "SIN-2-2-01",
        "SIN-2-RS-01",
        "SDO-2",
        "STP-2",
        "STPH-2",
        "CWS-2-1",
        "ASP-2",
        "MSP-2",
        "TSB-2",
        "SWO-2",
    }
    for p in PRODUCTS.values():
        assert p.pairing_fr and p.pairing_en
        p.rorg_func_type  # noqa: B018
