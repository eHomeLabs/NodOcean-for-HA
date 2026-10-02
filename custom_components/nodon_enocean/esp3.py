"""Protocole série EnOcean ESP3 (clés USB300 / TCM310 et compatibles).

Module volontairement sans dépendance à Home Assistant pour être testable seul.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SYNC_BYTE = 0x55

# Types de paquets ESP3
PACKET_RADIO_ERP1 = 0x01
PACKET_RESPONSE = 0x02
PACKET_EVENT = 0x04
PACKET_COMMON_COMMAND = 0x05

# Commandes communes
CO_RD_VERSION = 0x03
CO_RD_IDBASE = 0x08

RET_OK = 0x00

# RORG
RORG_RPS = 0xF6
RORG_1BS = 0xD5
RORG_4BS = 0xA5
RORG_VLD = 0xD2
RORG_UTE = 0xD4
RORG_ADT = 0xA6
RORG_MSC = 0xD1

BROADCAST_ID = 0xFFFFFFFF

_CRC8_TABLE: list[int] = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = ((_c << 1) ^ 0x07) & 0xFF if _c & 0x80 else (_c << 1) & 0xFF
    _CRC8_TABLE.append(_c)


def crc8(data: bytes | bytearray) -> int:
    """CRC8 ESP3 (polynôme 0x07)."""
    crc = 0
    for byte in data:
        crc = _CRC8_TABLE[crc ^ byte]
    return crc


def id_to_str(device_id: int) -> str:
    """Identifiant EnOcean au format 'AABBCCDD'."""
    return f"{device_id:08X}"


def str_to_id(text: str) -> int:
    """Convertit 'AA:BB:CC:DD', 'AABBCCDD' ou '0xAABBCCDD' en entier."""
    cleaned = text.strip().upper().replace(":", "").replace("-", "").replace(" ", "")
    if cleaned.startswith("0X"):
        cleaned = cleaned[2:]
    if len(cleaned) != 8:
        raise ValueError(f"Identifiant EnOcean invalide : {text}")
    return int(cleaned, 16)


@dataclass
class Packet:
    """Paquet ESP3 brut."""

    packet_type: int
    data: bytes
    optional: bytes = b""

    def encode(self) -> bytes:
        """Sérialise le paquet (sync + header + CRC + data + optional + CRC)."""
        header = bytes(
            [
                (len(self.data) >> 8) & 0xFF,
                len(self.data) & 0xFF,
                len(self.optional) & 0xFF,
                self.packet_type,
            ]
        )
        body = self.data + self.optional
        return bytes([SYNC_BYTE]) + header + bytes([crc8(header)]) + body + bytes([crc8(body)])


@dataclass
class RadioTelegram:
    """Télégramme radio ERP1 décodé."""

    rorg: int
    payload: bytes
    sender: int
    status: int = 0
    destination: int = BROADCAST_ID
    dbm: int | None = None
    raw: bytes = field(default=b"", repr=False)

    @property
    def sender_str(self) -> str:
        return id_to_str(self.sender)

    @property
    def is_broadcast(self) -> bool:
        return self.destination == BROADCAST_ID


def parse_radio(packet: Packet) -> RadioTelegram | None:
    """Décode un paquet RADIO_ERP1 (gère aussi les télégrammes adressés ADT)."""
    data = packet.data
    if packet.packet_type != PACKET_RADIO_ERP1 or len(data) < 6:
        return None
    rorg = data[0]
    destination = BROADCAST_ID
    dbm = None
    opt = packet.optional
    if len(opt) >= 6:
        destination = int.from_bytes(opt[1:5], "big")
        dbm = -opt[5]
    if rorg == RORG_ADT and len(data) >= 11:
        # A6 | RORG | payload | dest(4) | sender(4) | status
        rorg = data[1]
        payload = bytes(data[2:-9])
        destination = int.from_bytes(data[-9:-5], "big")
    else:
        payload = bytes(data[1:-5])
    sender = int.from_bytes(data[-5:-1], "big")
    status = data[-1]
    return RadioTelegram(
        rorg=rorg,
        payload=payload,
        sender=sender,
        status=status,
        destination=destination,
        dbm=dbm,
        raw=bytes(data),
    )


def build_radio(
    rorg: int,
    payload: bytes,
    sender: int,
    destination: int = BROADCAST_ID,
    status: int = 0x00,
) -> Packet:
    """Construit un paquet RADIO_ERP1 à émettre.

    Si une destination est donnée, la clé émet un télégramme adressé (ADT).
    """
    data = bytes([rorg]) + bytes(payload) + sender.to_bytes(4, "big") + bytes([status])
    optional = bytes([0x03]) + destination.to_bytes(4, "big") + bytes([0xFF, 0x00])
    return Packet(PACKET_RADIO_ERP1, data, optional)


def build_common_command(command: int, extra: bytes = b"") -> Packet:
    return Packet(PACKET_COMMON_COMMAND, bytes([command]) + extra)


class ESP3Parser:
    """Découpe un flux série en paquets ESP3 (robuste aux octets parasites)."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> list[Packet]:
        self._buffer.extend(chunk)
        packets: list[Packet] = []
        buf = self._buffer
        while True:
            try:
                start = buf.index(SYNC_BYTE)
            except ValueError:
                buf.clear()
                break
            if start:
                del buf[:start]
            if len(buf) < 6:
                break
            header = bytes(buf[1:5])
            if crc8(header) != buf[5]:
                # Faux octet de synchro : on avance d'un octet.
                del buf[0]
                continue
            data_len = (header[0] << 8) | header[1]
            opt_len = header[2]
            total = 6 + data_len + opt_len + 1
            if len(buf) < total:
                break
            body = bytes(buf[6 : 6 + data_len + opt_len])
            if crc8(body) != buf[total - 1]:
                del buf[0]
                continue
            packets.append(Packet(header[3], body[:data_len], body[data_len:]))
            del buf[:total]
        return packets


# --- UTE (Universal Teach-in) ---------------------------------------------------


@dataclass
class UteRequest:
    """Requête UTE émise par un appareil."""

    bidirectional: bool
    response_expected: bool
    request_type: int  # 0 = teach-in, 1 = suppression, 2 = non spécifié
    channels: int
    manufacturer: int
    rorg: int
    func: int
    type_: int
    raw: bytes

    @property
    def eep(self) -> str:
        return f"{self.rorg:02X}-{self.func:02X}-{self.type_:02X}"


def parse_ute(telegram: RadioTelegram) -> UteRequest | None:
    """Décode une requête UTE (RORG D4, CMD 0)."""
    p = telegram.payload
    if telegram.rorg != RORG_UTE or len(p) != 7:
        return None
    db6 = p[0]
    if db6 & 0x0F != 0:  # CMD 0 = requête
        return None
    return UteRequest(
        bidirectional=bool(db6 & 0x80),
        # bit 6 : 0 = réponse attendue, 1 = pas de réponse attendue
        response_expected=not bool(db6 & 0x40),
        request_type=(db6 >> 4) & 0x03,
        channels=p[1],
        manufacturer=p[2] | ((p[3] & 0x07) << 8),
        type_=p[4],
        func=p[5],
        rorg=p[6],
        raw=bytes(p),
    )


def build_ute_response(request: UteRequest, accepted: bool = True) -> bytes:
    """Charge utile UTE de réponse (CMD 1), à adresser à l'appareil.

    DB6 = 0x91 pour « bidirectionnel, teach-in accepté » (cf. notices NodOn).
    """
    result = 0x01 if accepted else 0x03
    db6 = 0x80 | (result << 4) | 0x01
    p = request.raw
    return bytes([db6, p[1], p[2], p[3], p[4], p[5], p[6]])
