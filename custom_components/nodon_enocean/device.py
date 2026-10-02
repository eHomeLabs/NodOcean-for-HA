"""Objet d'exécution représentant un produit NodOn appairé."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from typing import Any

from . import eep
from .catalog import Product
from .esp3 import RORG_VLD, RadioTelegram, id_to_str
from .gateway import Gateway, GatewayError

_LOGGER = logging.getLogger(__name__)

PILOT_WIRE_MODES = ["off", "comfort", "eco", "frost_protection", "comfort_1", "comfort_2"]


class NodOnDevice:
    """État et commandes d'un produit, alimenté par les télégrammes reçus."""

    def __init__(
        self,
        gateway: Gateway,
        product: Product,
        device_id: int,
        sender_offset: int | None,
        subentry_id: str,
        title: str,
    ) -> None:
        self.gateway = gateway
        self.product = product
        self.device_id = device_id
        self.sender_offset = sender_offset
        self.subentry_id = subentry_id
        self.title = title
        self.state: dict[str, Any] = {}
        self.last_dbm: int | None = None
        self._listeners: list[Callable[[set[str]], None]] = []
        self._unsub: Callable[[], None] | None = None

    @property
    def id_str(self) -> str:
        return id_to_str(self.device_id)

    @property
    def eep_code(self) -> str:
        return self.product.eep

    def start(self) -> None:
        self._unsub = self.gateway.subscribe(self.device_id, self._on_telegram)

    def stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    def add_listener(self, cb: Callable[[set[str]], None]) -> Callable[[], None]:
        self._listeners.append(cb)
        return lambda: self._listeners.remove(cb)

    # -- Réception -----------------------------------------------------------

    def decode(self, telegram: RadioTelegram) -> dict[str, Any] | None:
        code = self.product.eep
        if code.startswith("D2-01"):
            return eep.decode_d201(telegram, self.product.channels)
        if code == "D2-05-00":
            return eep.decode_d205(telegram)
        if code == "D5-00-01":
            return eep.decode_d50001(telegram)
        if code == "A5-02-05":
            return eep.decode_a50205(telegram)
        if code == "A5-04-01":
            return eep.decode_a50401(telegram)
        if code == "F6-02-01":
            return eep.decode_f60201(telegram)
        if code == "D2-03-0A":
            return eep.decode_d2030a(telegram)
        return None

    def _on_telegram(self, telegram: RadioTelegram) -> None:
        self.last_dbm = telegram.dbm
        changes = self.decode(telegram)
        keys: set[str] = {"rssi"}
        if changes:
            self.state.update(changes)
            keys |= set(changes)
        else:
            _LOGGER.debug(
                "%s (%s) : télégramme non interprété RORG=%02X %s",
                self.title,
                self.id_str,
                telegram.rorg,
                telegram.payload.hex(" "),
            )
        for cb in list(self._listeners):
            cb(keys)

    # -- Commandes -----------------------------------------------------------

    async def _send(self, payload: bytes) -> None:
        if self.sender_offset is None:
            raise GatewayError(f"{self.title} n'est pas un actionneur")
        await self.gateway.send_radio(
            RORG_VLD,
            payload,
            self.gateway.sender_id(self.sender_offset),
            self.device_id,
        )

    async def set_output(self, channel: int, on: bool) -> None:
        await self._send(eep.d201_set_output(channel, on))

    async def set_pilot_wire(self, mode: str) -> None:
        await self._send(eep.d201_pilot_wire_set(PILOT_WIRE_MODES.index(mode)))

    async def cover_position(self, ha_position: int) -> None:
        await self._send(eep.d205_go_to(ha_position))

    async def cover_stop(self) -> None:
        await self._send(eep.d205_stop())

    async def refresh(self) -> None:
        """Interroge l'actionneur (état, mesures)."""
        code = self.product.eep
        try:
            if code == "D2-05-00":
                await self._send(eep.d205_query())
                return
            if code == "D2-01-0C":
                await self._send(eep.d201_pilot_wire_query())
            elif self.product.channels > 1:
                for ch in range(self.product.channels):
                    await self._send(eep.d201_status_query(ch))
                    await asyncio.sleep(0.1)
            else:
                await self._send(eep.d201_status_query())
            if self.product.metering:
                await asyncio.sleep(0.1)
                await self._send(eep.d201_measurement_query(power=True))
                await asyncio.sleep(0.1)
                await self._send(eep.d201_measurement_query(power=False))
        except GatewayError as err:
            _LOGGER.debug("Interrogation de %s impossible : %s", self.title, err)
