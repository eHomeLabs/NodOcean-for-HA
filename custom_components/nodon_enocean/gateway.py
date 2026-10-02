"""Gestion de la clé EnOcean (USB300 / TCM310) en asyncio."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging

from .esp3 import (
    CO_RD_IDBASE,
    CO_RD_VERSION,
    PACKET_RADIO_ERP1,
    PACKET_RESPONSE,
    RET_OK,
    RORG_UTE,
    ESP3Parser,
    Packet,
    RadioTelegram,
    UteRequest,
    build_common_command,
    build_radio,
    build_ute_response,
    id_to_str,
    parse_radio,
    parse_ute,
)

_LOGGER = logging.getLogger(__name__)

TelegramCallback = Callable[[RadioTelegram], None]


class GatewayError(Exception):
    """Erreur de communication avec la clé."""


class GatewayOpenError(GatewayError):
    """Le port série ne peut pas être ouvert (occupé, droits, absent)."""


class GatewayNoResponse(GatewayError):
    """Le port s'ouvre mais aucune réponse ESP3 (pas une clé EnOcean ?)."""


@dataclass
class GatewayInfo:
    base_id: int
    chip_id: int | None = None
    app_version: str | None = None
    description: str | None = None


class _SerialProtocol(asyncio.Protocol):
    def __init__(self, gateway: Gateway) -> None:
        self._gateway = gateway

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._gateway._transport = transport  # type: ignore[assignment]

    def data_received(self, data: bytes) -> None:
        self._gateway._data_received(data)

    def connection_lost(self, exc: Exception | None) -> None:
        self._gateway._connection_lost(exc)


class Gateway:
    """Interface asynchrone vers une clé EnOcean ESP3."""

    def __init__(self, port: str) -> None:
        self.port = port
        self.info: GatewayInfo | None = None
        self._transport: asyncio.Transport | None = None
        self._parser = ESP3Parser()
        self._listeners: dict[int, list[TelegramCallback]] = {}
        self._global_listeners: list[TelegramCallback] = []
        self._response_waiter: asyncio.Future[Packet] | None = None
        self._lock = asyncio.Lock()
        self.on_disconnect: Callable[[], None] | None = None

    # -- Connexion -----------------------------------------------------------

    async def connect(self) -> GatewayInfo:
        import serial_asyncio_fast  # noqa: PLC0415

        loop = asyncio.get_running_loop()
        try:
            await serial_asyncio_fast.create_serial_connection(
                loop, lambda: _SerialProtocol(self), self.port, baudrate=57600
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Impossible d'ouvrir %s : %s", self.port, err)
            raise GatewayOpenError(str(err)) from err
        # Laisse le temps à la clé de démarrer et vide d'éventuels octets parasites.
        await asyncio.sleep(0.3)
        self._parser = ESP3Parser()
        last_err: GatewayError | None = None
        for attempt in range(1, 4):
            try:
                self.info = await self._read_info()
                return self.info
            except GatewayError as err:
                last_err = err
                _LOGGER.warning(
                    "Clé EnOcean sur %s : pas de réponse (essai %s/3) : %s",
                    self.port,
                    attempt,
                    err,
                )
                await asyncio.sleep(0.5)
        self.close()
        _LOGGER.error(
            "Aucune réponse ESP3 sur %s. Ce port n'est peut-être pas une clé EnOcean, "
            "ou il est utilisé par une autre intégration / un autre add-on.",
            self.port,
        )
        raise GatewayNoResponse(str(last_err))

    async def connect_transport(self, transport: asyncio.Transport) -> GatewayInfo:
        """Utilisé par les tests : transport déjà ouvert."""
        self._transport = transport
        self.info = await self._read_info()
        return self.info

    def close(self) -> None:
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    async def _read_info(self) -> GatewayInfo:
        resp = await self.command(build_common_command(CO_RD_IDBASE))
        if len(resp.data) < 5 or resp.data[0] != RET_OK:
            raise GatewayError("Lecture du Base ID impossible")
        info = GatewayInfo(base_id=int.from_bytes(resp.data[1:5], "big"))
        try:
            ver = await self.command(build_common_command(CO_RD_VERSION))
            d = ver.data
            if len(d) >= 13 and d[0] == RET_OK:
                info.app_version = ".".join(str(x) for x in d[1:5])
                info.chip_id = int.from_bytes(d[9:13], "big")
                info.description = d[17:33].split(b"\x00")[0].decode(errors="ignore") or None
        except GatewayError:
            pass
        _LOGGER.info(
            "Clé EnOcean prête sur %s (Base ID %s, Chip ID %s)",
            self.port,
            id_to_str(info.base_id),
            id_to_str(info.chip_id) if info.chip_id else "?",
        )
        return info

    # -- Émission ------------------------------------------------------------

    def _write(self, packet: Packet) -> None:
        if self._transport is None:
            raise GatewayError("Clé EnOcean non connectée")
        self._transport.write(packet.encode())

    async def command(self, packet: Packet, timeout: float = 2.0) -> Packet:
        """Envoie un paquet et attend la réponse ESP3 (RESPONSE)."""
        async with self._lock:
            loop = asyncio.get_running_loop()
            self._response_waiter = loop.create_future()
            self._write(packet)
            try:
                return await asyncio.wait_for(self._response_waiter, timeout)
            except TimeoutError as err:
                raise GatewayError("Pas de réponse de la clé EnOcean") from err
            finally:
                self._response_waiter = None

    async def send_radio(self, rorg: int, payload: bytes, sender: int, destination: int) -> None:
        """Émet un télégramme radio adressé."""
        resp = await self.command(build_radio(rorg, payload, sender, destination))
        if resp.data and resp.data[0] != RET_OK:
            raise GatewayError(f"La clé a refusé le télégramme (code {resp.data[0]})")

    def sender_id(self, offset: int) -> int:
        if self.info is None:
            raise GatewayError("Clé EnOcean non initialisée")
        if not 0 <= offset <= 127:
            raise GatewayError("Offset d'émetteur hors plage (0-127)")
        return self.info.base_id + offset

    async def send_ute_response(self, request: UteRequest, device_id: int, sender: int) -> None:
        await self.send_radio(RORG_UTE, build_ute_response(request, True), sender, device_id)

    # -- Réception -----------------------------------------------------------

    def _data_received(self, data: bytes) -> None:
        _LOGGER.debug("Octets reçus : %s", data.hex(" "))
        for packet in self._parser.feed(data):
            if packet.packet_type == PACKET_RESPONSE:
                if self._response_waiter and not self._response_waiter.done():
                    self._response_waiter.set_result(packet)
            elif packet.packet_type == PACKET_RADIO_ERP1:
                telegram = parse_radio(packet)
                if telegram is not None:
                    self._dispatch(telegram)

    def _dispatch(self, telegram: RadioTelegram) -> None:
        _LOGGER.debug(
            "RX %s RORG=%02X data=%s dBm=%s",
            telegram.sender_str,
            telegram.rorg,
            telegram.payload.hex(" "),
            telegram.dbm,
        )
        for cb in list(self._global_listeners):
            try:
                cb(telegram)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Erreur dans un écouteur global")
        for cb in list(self._listeners.get(telegram.sender, ())):
            try:
                cb(telegram)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Erreur de traitement pour %s", telegram.sender_str)

    def _connection_lost(self, exc: Exception | None) -> None:
        self._transport = None
        _LOGGER.warning("Connexion à la clé EnOcean perdue : %s", exc)
        if self.on_disconnect:
            self.on_disconnect()

    def subscribe(self, device_id: int, cb: TelegramCallback) -> Callable[[], None]:
        self._listeners.setdefault(device_id, []).append(cb)
        return lambda: self._listeners.get(device_id, []).remove(cb)

    def subscribe_all(self, cb: TelegramCallback) -> Callable[[], None]:
        self._global_listeners.append(cb)
        return lambda: self._global_listeners.remove(cb)

    def is_known(self, device_id: int) -> bool:
        return bool(self._listeners.get(device_id))


def is_ute(telegram: RadioTelegram) -> UteRequest | None:
    return parse_ute(telegram)
