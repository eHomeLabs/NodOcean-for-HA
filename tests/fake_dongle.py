"""Simulateur de clé USB300 pour les tests."""

from __future__ import annotations

import asyncio

from custom_components.nodon_enocean.esp3 import (
    CO_RD_IDBASE,
    CO_RD_VERSION,
    PACKET_COMMON_COMMAND,
    PACKET_RADIO_ERP1,
    PACKET_RESPONSE,
    ESP3Parser,
    Packet,
    RadioTelegram,
    parse_radio,
)

BASE_ID = 0xFF8A2C00
CHIP_ID = 0x0195ABCD


class FakeDongle(asyncio.Transport):
    def __init__(self) -> None:
        super().__init__()
        self.gateway = None
        self.sent: list[RadioTelegram] = []
        self._parser = ESP3Parser()
        self.closed = False
        self.on_send = None
        self.base_id = BASE_ID

    def attach(self, gateway) -> None:
        self.gateway = gateway

    def _reply(self, data: bytes) -> None:
        packet = Packet(PACKET_RESPONSE, data)
        asyncio.get_running_loop().call_soon(self.gateway._data_received, packet.encode())

    def write(self, data: bytes) -> None:
        for packet in self._parser.feed(data):
            if packet.packet_type == PACKET_COMMON_COMMAND:
                if packet.data[0] == CO_RD_IDBASE:
                    self._reply(b"\x00" + self.base_id.to_bytes(4, "big") + b"\x0a")
                elif packet.data[0] == CO_RD_VERSION:
                    desc = b"GATEWAYCTRL".ljust(16, b"\x00")
                    self._reply(
                        b"\x00"
                        + bytes([2, 11, 1, 0])
                        + bytes([2, 6, 3, 0])
                        + CHIP_ID.to_bytes(4, "big")
                        + b"\x45\x00\x01\x03"
                        + desc
                    )
            elif packet.packet_type == PACKET_RADIO_ERP1:
                telegram = parse_radio(packet)
                self.sent.append(telegram)
                self._reply(b"\x00")
                if self.on_send:
                    self.on_send(telegram)

    def inject(
        self, rorg: int, payload: bytes, sender: int, dbm: int = 60, status: int = 0
    ) -> None:
        """Simule la réception d'un télégramme radio (status : compteur de répétitions)."""
        data = bytes([rorg]) + payload + sender.to_bytes(4, "big") + bytes([status])
        opt = b"\x01\xff\xff\xff\xff" + bytes([dbm]) + b"\x00"
        self.gateway._data_received(Packet(PACKET_RADIO_ERP1, data, opt).encode())

    def close(self) -> None:
        self.closed = True

    def is_closing(self) -> bool:
        return self.closed
