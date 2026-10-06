"""Remote Management / Remote Commissioning (ReCom) EnOcean.

Sources : EnOcean Alliance « Remote Management » v2.9 et « Remote Commissioning »
v1.3, guides experts NodOn SIN-2-X-XX (V16) et SIN-2-RS-01 (V21), DDF NodOn.

Les messages ReMan circulent dans des télégrammes SYS_EX (RORG 0xC5) chaînés :
- télégramme IDX 0 : longueur (9 bits), fabricant (11 bits), fonction (12 bits)
  puis 4 octets de données ;
- télégrammes suivants : 8 octets de données.

Module sans dépendance à Home Assistant (testable seul).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time

RORG_SYS_EX = 0xC5
MANUFACTURER_MULTI = 0x7FF  # RMCC et RPC standard
MANUFACTURER_NODON = 0x046  # ID-RF / NodOn

# RMCC
FN_UNLOCK = 0x001
FN_LOCK = 0x002
FN_SET_CODE = 0x003
FN_QUERY_ID = 0x004
FN_ACTION = 0x005
FN_PING = 0x006
FN_QUERY_FUNCTION = 0x007
FN_QUERY_STATUS = 0x008
FN_PING_ANSWER = 0x606
FN_QUERY_STATUS_ANSWER = 0x608

# RPC Remote Commissioning
FN_GET_LINK_TABLE_METADATA = 0x210
FN_GET_LINK_TABLE = 0x211
FN_SET_LINK_TABLE = 0x212
FN_REMOTE_SET_LEARN = 0x220
FN_RESET_DEFAULTS = 0x224
FN_APPLY_CHANGES = 0x226
FN_GET_PRODUCT_ID = 0x227
FN_GET_DEVICE_CONFIG = 0x230
FN_SET_DEVICE_CONFIG = 0x231
FN_GET_LINK_CONFIG = 0x232
FN_SET_LINK_CONFIG = 0x233
FN_ACK = 0x240
FN_LINK_TABLE_METADATA_RESPONSE = 0x810
FN_LINK_TABLE_RESPONSE = 0x811
FN_PRODUCT_ID_RESPONSE = 0x827
FN_DEVICE_CONFIG_RESPONSE = 0x830
FN_LINK_CONFIG_RESPONSE = 0x832

CHAIN_PERIOD = 1.0  # s, délai maximal entre deux télégrammes d'un message
MAX_DATA = 508

# Codes retournés par « Query Status »
STATUS_CODES = {
    0x00: "OK",
    0x01: "wrong_target_id",
    0x02: "wrong_unlock_code",
    0x03: "wrong_eep",
    0x04: "wrong_manufacturer_id",
    0x05: "wrong_data_size",
    0x06: "no_code_set",
    0x07: "not_sent",
    0x08: "rpc_failed",
    0x09: "message_timeout",
    0x0A: "too_long_message",
    0x0B: "message_part_already_received",
    0x0C: "message_part_not_received",
    0x0D: "address_out_of_range",
    0x0E: "code_data_size_exceeded",
    0x0F: "wrong_data",
}

# Valeur « Channel Definition Enumeration » des Generic Profiles utilisée par les
# firmwares NodOn : type 0b11, signal 0x01, valeur courante 0b01, résolution 8 bits
# -> 0xC056 suivi de la valeur (ex. 0xC05601).
GP_ENUM_PREFIX = b"\xc0\x56"


@dataclass
class ReManMessage:
    """Message ReMan complet (après réassemblage)."""

    function: int
    manufacturer: int
    data: bytes
    sender: int = 0
    destination: int = 0xFFFFFFFF


# --- Encodage / décodage SYS_EX ----------------------------------------------------


def encode_message(function: int, data: bytes = b"", seq: int = 1,
                   manufacturer: int = MANUFACTURER_MULTI) -> list[bytes]:
    """Découpe un message en charges utiles SYS_EX de 9 octets."""
    data = bytes(data)
    if len(data) > MAX_DATA:
        raise ValueError("Message ReMan trop long")
    if not 1 <= seq <= 3:
        raise ValueError("SEQ doit valoir 1, 2 ou 3")
    header = ((len(data) & 0x1FF) << 23) | ((manufacturer & 0x7FF) << 12) | (function & 0xFFF)
    chunks = [bytes([seq << 6]) + header.to_bytes(4, "big") + data[:4].ljust(4, b"\x00")]
    rest = data[4:]
    idx = 1
    while rest:
        chunks.append(bytes([(seq << 6) | idx]) + rest[:8].ljust(8, b"\x00"))
        rest = rest[8:]
        idx += 1
    return chunks


@dataclass
class _Pending:
    started: float
    parts: dict[int, bytes] = field(default_factory=dict)
    length: int | None = None
    function: int = 0
    manufacturer: int = 0


class SysExAssembler:
    """Réassemble les télégrammes SYS_EX reçus en messages."""

    def __init__(self, clock=time.monotonic) -> None:
        self._pending: dict[tuple[int, int], _Pending] = {}
        self._clock = clock

    def feed(self, sender: int, payload: bytes, destination: int = 0xFFFFFFFF) -> ReManMessage | None:
        if len(payload) != 9:
            return None
        now = self._clock()
        # Messages incomplets trop anciens : abandonnés
        for key in [k for k, p in self._pending.items() if now - p.started > CHAIN_PERIOD * 3]:
            del self._pending[key]
        seq = payload[0] >> 6
        idx = payload[0] & 0x3F
        key = (sender, seq)
        if idx == 0:
            header = int.from_bytes(payload[1:5], "big")
            pending = _Pending(started=now)
            pending.length = header >> 23
            pending.manufacturer = (header >> 12) & 0x7FF
            pending.function = header & 0xFFF
            # Des morceaux suivants arrivés avant l'IDX 0 sont conservés.
            old = self._pending.get(key)
            if old is not None and old.length is None:
                pending.parts.update(old.parts)
            pending.parts[0] = bytes(payload[5:9])
            self._pending[key] = pending
        else:
            pending = self._pending.setdefault(key, _Pending(started=now))
            if idx in pending.parts:  # morceau déjà reçu : message corrompu
                del self._pending[key]
                return None
            pending.parts[idx] = bytes(payload[1:9])
        if pending.length is None:
            return None
        needed = 1 + max(0, (pending.length - 4 + 7) // 8)
        if any(i not in pending.parts for i in range(needed)):
            return None
        del self._pending[key]
        data = b"".join(pending.parts[i] for i in range(needed))[: pending.length]
        return ReManMessage(pending.function, pending.manufacturer, data, sender, destination)


# --- Valeurs de configuration -------------------------------------------------------


def gp_enum(value: int, size: int = 1) -> bytes:
    """Valeur encodée comme les firmwares NodOn (0xC056 + valeur)."""
    return GP_ENUM_PREFIX + int(value).to_bytes(size, "big")


def decode_value(raw: bytes) -> int:
    """Valeur entière d'un paramètre (préfixe 0xC056 retiré s'il est présent)."""
    raw = bytes(raw)
    if len(raw) > 2 and raw[:2] == GP_ENUM_PREFIX:
        raw = raw[2:]
    return int.from_bytes(raw, "big") if raw else 0


def encode_params(params: list[tuple[int, bytes]]) -> bytes:
    """Liste (index, valeur brute) -> index (2) + longueur (1) + valeur."""
    out = bytearray()
    for index, value in params:
        out += int(index).to_bytes(2, "big") + bytes([len(value)]) + bytes(value)
    return bytes(out)


def decode_params(data: bytes) -> dict[int, bytes]:
    """Index -> valeur brute (réponse « Get … Configuration »)."""
    params: dict[int, bytes] = {}
    pos = 0
    while pos + 3 <= len(data):
        index = int.from_bytes(data[pos : pos + 2], "big")
        length = data[pos + 2]
        pos += 3
        if pos + length > len(data):
            break
        params[index] = bytes(data[pos : pos + length])
        pos += length
    return params


# --- Commandes ---------------------------------------------------------------------


def set_code(code: int) -> tuple[int, bytes]:
    """Set Code (RMCC 0x003) : nouveau code de sécurité du produit."""
    return FN_SET_CODE, int(code).to_bytes(4, "big")


def random_code() -> int:
    """Code de sécurité aléatoire (00000000 et FFFFFFFF sont réservés)."""
    import secrets  # noqa: PLC0415

    while True:
        code = secrets.randbits(32)
        if code not in (0, 0xFFFFFFFF):
            return code


def unlock(code: int = 0) -> tuple[int, bytes]:
    return FN_UNLOCK, int(code).to_bytes(4, "big")


def query_status() -> tuple[int, bytes]:
    return FN_QUERY_STATUS, b""


def ping() -> tuple[int, bytes]:
    return FN_PING, b""


def get_link_table_metadata() -> tuple[int, bytes]:
    return FN_GET_LINK_TABLE_METADATA, b""


def get_link_table(start: int, end: int, outbound: bool = False) -> tuple[int, bytes]:
    return FN_GET_LINK_TABLE, bytes([0x80 if outbound else 0x00, start, end])


@dataclass
class LinkEntry:
    index: int
    device_id: int
    eep: tuple[int, int, int]
    channel: int

    @property
    def empty(self) -> bool:
        return self.device_id in (0, 0xFFFFFFFF) or self.eep == (0, 0, 0)

    @property
    def eep_str(self) -> str:
        return "-".join(f"{x:02X}" for x in self.eep)

    @property
    def id_str(self) -> str:
        return f"{self.device_id:08X}"

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "id": self.id_str,
            "eep": self.eep_str,
            "channel": self.channel,
        }


def link_entry_bytes(index: int, device_id: int, eep: tuple[int, int, int], channel: int) -> bytes:
    return bytes([index]) + device_id.to_bytes(4, "big") + bytes(eep) + bytes([channel])


def set_link_table(entries: list[bytes], outbound: bool = False) -> tuple[int, bytes]:
    return FN_SET_LINK_TABLE, bytes([0x80 if outbound else 0x00]) + b"".join(entries)


def delete_link(index: int) -> tuple[int, bytes]:
    """Suppression d'une entrée : identifiant, EEP et canal à zéro (firmware NodOn)."""
    return set_link_table([bytes([index]) + bytes(8)])


def remote_learn(mode: int, index: int = 0xFF) -> tuple[int, bytes]:
    """mode : 0 apprentissage, 1 désapprentissage, 2 sortie du mode."""
    return FN_REMOTE_SET_LEARN, bytes([(mode & 0x03) << 6, index])


def reset_defaults(config: bool, inbound: bool, outbound: bool = False) -> tuple[int, bytes]:
    flags = (0x80 if config else 0) | (0x40 if inbound else 0) | (0x20 if outbound else 0)
    return FN_RESET_DEFAULTS, bytes([flags])


def get_product_id() -> tuple[int, bytes]:
    return FN_GET_PRODUCT_ID, b""


def get_device_config(start: int, end: int, length: int = 0) -> tuple[int, bytes]:
    return FN_GET_DEVICE_CONFIG, start.to_bytes(2, "big") + end.to_bytes(2, "big") + bytes([length])


def set_device_config(params: list[tuple[int, bytes]]) -> tuple[int, bytes]:
    return FN_SET_DEVICE_CONFIG, encode_params(params)


def get_link_config(link_index: int, start: int, end: int, length: int = 0) -> tuple[int, bytes]:
    return (
        FN_GET_LINK_CONFIG,
        bytes([0x00, link_index]) + start.to_bytes(2, "big") + end.to_bytes(2, "big") + bytes([length]),
    )


def set_link_config(link_index: int, params: list[tuple[int, bytes]]) -> tuple[int, bytes]:
    return FN_SET_LINK_CONFIG, bytes([0x00, link_index]) + encode_params(params)


# --- Réponses ----------------------------------------------------------------------


def parse_link_table_metadata(data: bytes) -> dict | None:
    if len(data) < 5:
        return None
    flags = data[0]
    return {
        "remote_teach_outbound": bool(flags & 0x80),
        "remote_teach_inbound": bool(flags & 0x40),
        "outbound_table": bool(flags & 0x20),
        "inbound_table": bool(flags & 0x10),
        "outbound_length": data[1],
        "outbound_max": data[2],
        "inbound_length": data[3],
        "inbound_max": data[4],
    }


def parse_link_table(data: bytes) -> list[LinkEntry]:
    entries = []
    body = data[1:]
    for pos in range(0, len(body) - 8, 9):
        chunk = body[pos : pos + 9]
        entries.append(
            LinkEntry(
                index=chunk[0],
                device_id=int.from_bytes(chunk[1:5], "big"),
                eep=(chunk[5], chunk[6], chunk[7]),
                channel=chunk[8],
            )
        )
    return entries


def parse_link_config(data: bytes) -> tuple[int, dict[int, bytes]] | None:
    if len(data) < 2:
        return None
    return data[1], decode_params(data[2:])


def parse_query_status(data: bytes) -> dict | None:
    if len(data) < 4:
        return None
    return {
        "code_set": bool(data[0] & 0x80),
        "last_seq": data[0] & 0x03,
        "last_function": ((data[1] & 0x0F) << 8) | data[2],
        "return_code": data[3],
        "status": STATUS_CODES.get(data[3], f"0x{data[3]:02X}"),
    }


def parse_product_id(data: bytes) -> str | None:
    if len(data) < 6:
        return None
    return data[:6].hex().upper()
