"""Remote Commissioning (v0.7) : trames SYS_EX, volet SIN-2-RS-01, télécommandes."""

from __future__ import annotations

import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from custom_components.nodon_enocean import eep, recom
from custom_components.nodon_enocean.const import DOMAIN

from .test_integration import _pair, _setup_gateway

RS = 0x0512AB40
SIN21 = 0x0512AB34
REMOTE = 0xFEF00011


def _hex(b: bytes) -> str:
    return b.hex(" ").upper()


# --- Trames ----------------------------------------------------------------------


def test_sysex_encoding() -> None:
    # Unlock, code 0 : longueur 4, fabricant 0x7FF, fonction 0x001
    chunks = recom.encode_message(*recom.unlock(0), seq=1)
    assert [_hex(c) for c in chunks] == ["40 02 7F F0 01 00 00 00 00"]
    # Get Link Table Metadata : pas de données
    assert _hex(recom.encode_message(*recom.get_link_table_metadata())[0]) == (
        "40 00 7F F2 10 00 00 00 00"
    )
    # Exemple du guide expert : type d'interrupteur 1 -> 00 00 03 C0 56 01
    fn, data = recom.set_device_config([(0, recom.gp_enum(1))])
    assert fn == 0x231 and _hex(data) == "00 00 03 C0 56 01"
    # Exemple du guide : 2e télécommande, bouton BI, 25 %
    fn, data = recom.set_link_config(1, [(0, recom.gp_enum(3)), (1, recom.gp_enum(0x19))])
    assert _hex(data) == "00 01 00 00 03 C0 56 03 00 01 03 C0 56 19"
    assert recom.decode_value(bytes.fromhex("C0 56 64")) == 100
    assert recom.decode_value(bytes.fromhex("C0 56 0B B8")) == 3000
    assert recom.decode_value(b"\x02") == 2
    # Suppression d'une entrée : tout à zéro
    assert _hex(recom.delete_link(5)[1]) == "00 05 00 00 00 00 00 00 00 00"


def test_sysex_reassembly() -> None:
    entries = [
        recom.link_entry_bytes(i, 0xFEF00000 + i, (0xF6, 0x02, 0x01), 0) for i in range(3)
    ]
    fn, data = recom.set_link_table(entries)
    chunks = recom.encode_message(fn, data, seq=2)
    assert len(chunks) == 4  # 28 octets = 4 + 8 + 8 + 8
    asm = recom.SysExAssembler()
    # Ordre mélangé : l'IDX 0 arrive en dernier
    for chunk in chunks[1:]:
        assert asm.feed(0x01020304, chunk) is None
    message = asm.feed(0x01020304, chunks[0])
    assert message and message.function == fn and message.data == data
    assert message.manufacturer == recom.MANUFACTURER_MULTI
    # Réponse de table : 3 entrées décodées
    table = recom.parse_link_table(data)
    assert [e.id_str for e in table] == ["FEF00000", "FEF00001", "FEF00002"]
    assert table[0].eep_str == "F6-02-01" and not table[0].empty
    status = recom.parse_query_status(bytes([0x80, 0x02, 0x31, 0x0F]))
    assert status == {
        "code_set": True,
        "last_seq": 0,
        "last_function": 0x231,
        "return_code": 0x0F,
        "status": "wrong_data",
    }


def test_vld_frames() -> None:
    # Guide expert SIN-2-RS-01 : 60,32 s -> 17 90 00 00 05
    assert _hex(eep.d205_set_travel_time(60.32)) == "17 90 00 00 05"
    assert _hex(eep.d205_set_travel_time(1)) == "01 F4 00 00 05"  # minimum 5 s
    # Interrupteur 2 états : mode 1 + bit 5
    assert _hex(eep.d201_set_ext_interface(0, 0, 0, 1, True)) == "0B 00 00 00 00 00 60"
    assert _hex(eep.d201_set_ext_interface(0, 0, 0, 2)) == "0B 00 00 00 00 00 80"


# --- Produit simulé ---------------------------------------------------------------


class FakeReComDevice:
    """Module NodOn répondant au Remote Commissioning (valeurs 0xC056xx)."""

    def __init__(self, dongle, device_id: int) -> None:
        self.dongle = dongle
        self.device_id = device_id
        self.links: dict[int, bytes] = {
            0: bytes.fromhex("FE F0 00 01 F6 02 01 00"),
            1: bytes.fromhex("FE F0 00 02 F6 04 01 FF"),
        }
        self.config = {0: 1, 1: 1, 2: 3000, 4: 3100}
        self.link_config: dict[int, dict[int, bytes]] = {}
        self.received: list[tuple[int, bytes]] = []
        self.mute = False
        self._asm = recom.SysExAssembler()
        previous = dongle.on_send

        def on_send(telegram) -> None:
            if previous:
                previous(telegram)
            if telegram.rorg == recom.RORG_SYS_EX and telegram.destination == device_id:
                message = self._asm.feed(telegram.sender, telegram.payload)
                if message is not None:
                    asyncio.get_running_loop().call_soon(self._handle, message)

        dongle.on_send = on_send

    def _reply(self, function: int, data: bytes = b"") -> None:
        for chunk in recom.encode_message(function, data, seq=2, manufacturer=0x046):
            self.dongle.inject(recom.RORG_SYS_EX, chunk, self.device_id)

    def _handle(self, message: recom.ReManMessage) -> None:
        fn, data = message.function, message.data
        self.received.append((fn, data))
        if self.mute:
            return
        if fn in (recom.FN_UNLOCK, recom.FN_SET_DEVICE_CONFIG):
            if fn == recom.FN_SET_DEVICE_CONFIG:
                for index, raw in recom.decode_params(data).items():
                    self.config[index] = recom.decode_value(raw)
            self._reply(recom.FN_ACK)
        elif fn == recom.FN_QUERY_STATUS:
            self._reply(recom.FN_QUERY_STATUS_ANSWER, bytes([0, 0, 0, 0]))
        elif fn == recom.FN_GET_LINK_TABLE_METADATA:
            self._reply(recom.FN_LINK_TABLE_METADATA_RESPONSE, bytes([0x50, 0, 0, len(self.links), 24]))
        elif fn == recom.FN_GET_LINK_TABLE:
            start, end = data[1], data[2]
            indexes = list(range(start, end + 1))
            # Comme le firmware : réponse découpée en plusieurs messages
            for pos in range(0, len(indexes), 3):
                body = b"".join(
                    bytes([i]) + self.links.get(i, bytes(8)) for i in indexes[pos : pos + 3]
                )
                self._reply(recom.FN_LINK_TABLE_RESPONSE, b"\x00" + body)
        elif fn == recom.FN_SET_LINK_TABLE:
            body = data[1:]
            for pos in range(0, len(body), 9):
                index, entry = body[pos], body[pos + 1 : pos + 9]
                if entry == bytes(8):
                    self.links.pop(index, None)
                else:
                    self.links[index] = entry
            self._reply(recom.FN_ACK)
        elif fn == recom.FN_GET_DEVICE_CONFIG:
            start = int.from_bytes(data[0:2], "big")
            size = 2 if start in (2, 4) else 1
            value = recom.gp_enum(self.config[start], size)
            self._reply(
                recom.FN_DEVICE_CONFIG_RESPONSE, recom.encode_params([(start, value)])
            )
        elif fn == recom.FN_SET_LINK_CONFIG:
            self.link_config[data[1]] = recom.decode_params(data[2:])
            self._reply(recom.FN_ACK)


def _entity(hass, platform: str, key: str, device: int = RS) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{device:08X}_{key}")
    assert entity_id, key
    return entity_id


async def test_roller_shutter_recom(hass: HomeAssistant, dongle) -> None:
    fake = FakeReComDevice(dongle, RS)
    entry = await _setup_gateway(hass)
    entry = await _pair(
        hass,
        entry,
        dongle,
        "SIN-2-RS-01",
        lambda: dongle.inject(0xD4, bytes.fromhex("A0 01 46 00 00 05 D2"), RS),
        "Volet",
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    # Lecture au démarrage : type d'interrupteur et temps calibrés
    assert recom.FN_UNLOCK in [fn for fn, _ in fake.received]
    assert hass.states.get(_entity(hass, "select", "rs_switch_type")).state == "type_1"
    assert float(hass.states.get(_entity(hass, "sensor", "rs_time_down")).state) == 60.0
    assert float(hass.states.get(_entity(hass, "sensor", "rs_time_up")).state) == 62.0
    assert hass.states.get(_entity(hass, "sensor", "rs_calibration_type")).state == "classic"

    # Type d'interrupteur 4 (poussoirs)
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": _entity(hass, "select", "rs_switch_type"), "option": "type_4"},
        blocking=True,
    )
    assert fake.config[0] == 4
    assert (recom.FN_SET_DEVICE_CONFIG, bytes.fromhex("00 00 03 C0 56 04")) in fake.received

    # Calibration complète puis arrêt
    for kind, value in (("complex", 2), ("stop", 3)):
        await hass.services.async_call(
            "button", "press", {"entity_id": _entity(hass, "button", f"calibration_{kind}")},
            blocking=True,
        )
        assert fake.config[1] == value

    # Temps de course (VLD D2-05 CMD 0x5)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": _entity(hass, "number", "travel_time"), "value": 60.32},
        blocking=True,
    )
    vld = [t.payload for t in dongle.sent if t.rorg == 0xD2 and t.destination == RS]
    assert bytes.fromhex("17 90 00 00 05") in vld

    # Lecture des télécommandes appairées
    await hass.services.async_call(
        "button", "press", {"entity_id": _entity(hass, "button", "recom_read")}, blocking=True
    )
    links = hass.states.get(_entity(hass, "sensor", "paired_devices"))
    assert links.state == "2"
    assert links.attributes["devices"][0] == "FEF00001 (F6-02-01, index 0)"


async def test_paired_remotes_flow(hass: HomeAssistant, dongle) -> None:
    fake = FakeReComDevice(dongle, RS)
    entry = await _setup_gateway(hass)
    entry = await _pair(
        hass,
        entry,
        dongle,
        "SIN-2-RS-01",
        lambda: dongle.inject(0xD4, bytes.fromhex("A0 01 46 00 00 05 D2"), RS),
        "Volet",
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    subentry_id = next(iter(entry.subentries))

    async def _open_menu():
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "device"),
            context={"source": "reconfigure", "subentry_id": subentry_id},
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()
        result = await hass.config_entries.subentries.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.MENU, result
        return result

    # Ajout d'une télécommande par son identifiant (1re entrée libre : 2)
    menu = await _open_menu()
    assert "FEF00001" in menu["description_placeholders"]["links"]
    assert menu["menu_options"] == ["links_add", "links_remove", "rs_position"]
    result = await hass.config_entries.subentries.async_configure(
        menu["flow_id"], {"next_step_id": "links_add"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"device_id": "zz", "link_type": "rocker_b"}
    )
    assert result["errors"] == {"device_id": "invalid_id"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"device_id": f"{REMOTE:08X}", "link_type": "rocker_b"}
    )
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "links_updated"
    assert fake.links[2] == bytes.fromhex("FE F0 00 11 F6 02 01 01")

    # Position atteinte : bouton BI, ouverture 75 % (module : 25 %)
    menu = await _open_menu()
    result = await hass.config_entries.subentries.async_configure(
        menu["flow_id"], {"next_step_id": "rs_position"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"link": "2", "trigger": "bi", "position": 75}
    )
    assert result["reason"] == "links_updated"
    assert fake.link_config[2] == {0: bytes.fromhex("C0 56 03"), 1: bytes.fromhex("C0 56 19")}

    # Suppression de deux télécommandes
    menu = await _open_menu()
    result = await hass.config_entries.subentries.async_configure(
        menu["flow_id"], {"next_step_id": "links_remove"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"links": ["0", "2"]}
    )
    assert result["reason"] == "links_updated"
    assert set(fake.links) == {1}


async def test_recom_no_answer(hass: HomeAssistant, dongle) -> None:
    fake = FakeReComDevice(dongle, SIN21)
    fake.mute = True
    entry = await _setup_gateway(hass)
    entry = await _pair(
        hass,
        entry,
        dongle,
        "SIN-2-1-01",
        lambda: dongle.inject(0xD4, bytes.fromhex("A0 01 46 00 0F 01 D2"), SIN21),
        "Lampe",
    )
    subentry_id = next(iter(entry.subentries))
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": "reconfigure", "subentry_id": subentry_id},
    )
    await hass.async_block_till_done()
    while result["type"] is FlowResultType.SHOW_PROGRESS:
        await asyncio.sleep(0.5)
        result = await hass.config_entries.subentries.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "recom_no_answer"


async def test_sin_switch_type(hass: HomeAssistant, dongle) -> None:
    entry = await _setup_gateway(hass)
    await _pair(
        hass,
        entry,
        dongle,
        "SIN-2-1-01",
        lambda: dongle.inject(0xD4, bytes.fromhex("A0 01 46 00 0F 01 D2"), SIN21),
        "Lampe",
    )
    select = _entity(hass, "select", "switch_type", SIN21)
    assert hass.states.get(select).state == "auto"
    await hass.services.async_call(
        "select", "select_option", {"entity_id": select, "option": "switch_2_state"},
        blocking=True,
    )
    assert dongle.sent[-1].payload == bytes.fromhex("0B 00 00 00 00 00 60")
    # Une minuterie réglée ensuite garde le mode « 2 états »
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": _entity(hass, "number", "auto_off_0", SIN21), "value": 10},
        blocking=True,
    )
    assert dongle.sent[-1].payload == bytes.fromhex("0B 00 00 64 00 00 60")
    # Commande locale et télécommandes appairées en direct (CMD 0x2)
    taught = _entity(hass, "switch", "taught_in", SIN21)
    _entity(hass, "switch", "local_control", SIN21)
    await hass.services.async_call("switch", "turn_off", {"entity_id": taught}, blocking=True)
    assert dongle.sent[-1].payload == eep.d201_set_local(taught_in=False)
    # Pas de bouton de calibration sur un module de commutation
    assert er.async_get(hass).async_get_entity_id(
        "button", DOMAIN, f"{SIN21:08X}_calibration_classic"
    ) is None


# --- Code de sécurité (préfixe + 4 derniers caractères de l'ID) ---------------------


def test_recom_prefix() -> None:
    assert recom.parse_prefix("") is None
    assert recom.parse_prefix(" 1234 ") == 0x1234
    assert recom.parse_prefix("0xab12") == 0xAB12
    for bad in ("123", "12345", "12G4"):
        try:
            recom.parse_prefix(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    assert recom.derived_code(0x1234, 0x0512E662) == 0x1234E662


async def test_unlock_with_prefix(hass: HomeAssistant, dongle) -> None:
    """Code 00000000 refusé : l'intégration essaie le code dérivé 1234 + ID."""
    fake = FakeReComDevice(dongle, SIN21)
    code = recom.derived_code(0x1234, SIN21)
    original = fake._handle

    def _handle(message):
        if message.function == recom.FN_UNLOCK:
            fake.received.append((message.function, message.data))
            if int.from_bytes(message.data, "big") == code:
                fake._reply(recom.FN_ACK)
            return
        original(message)

    fake._handle = _handle
    entry = await _setup_gateway(hass)

    # Option de la clé : préfixe invalide refusé, puis 1234 accepté
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"mqtt_enabled": False, "advanced": {}, "recom": {"recom_prefix": "12G4"}}
    )
    assert result["errors"] == {"base": "invalid_recom_prefix"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"mqtt_enabled": False, "advanced": {}, "recom": {"recom_prefix": "1234"}}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry.options["recom"] == {"recom_prefix": "1234"}
    assert entry.runtime_data.gateway.recom_prefix == 0x1234

    entry = await _pair(
        hass,
        entry,
        dongle,
        "SIN-2-1-01",
        lambda: dongle.inject(0xD4, bytes.fromhex("A0 01 46 00 0F 01 D2"), SIN21),
        "Lampe",
    )
    await hass.services.async_call(
        "button", "press", {"entity_id": _entity(hass, "button", "recom_read", SIN21)},
        blocking=True,
    )
    unlocks = [int.from_bytes(d, "big") for fn, d in fake.received if fn == recom.FN_UNLOCK]
    assert unlocks == [0, code]
    assert hass.states.get(_entity(hass, "sensor", "paired_devices", SIN21)).state == "2"
