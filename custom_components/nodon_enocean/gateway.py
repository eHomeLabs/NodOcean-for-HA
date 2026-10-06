"""Gestion de la clé EnOcean (USB300 / TCM310) en asyncio."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
import logging
import time

from . import recom
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
ReManCallback = Callable[[recom.ReManMessage], None]

# Déverrouillage ReCom renouvelé avant la fin de la fenêtre de 15 min des produits
UNLOCK_RENEW = 10 * 60  # s

# ESP3 : paquet REMOTE_MAN_COMMAND (la clé peut remonter les messages ReMan ainsi)
PACKET_REMOTE_MAN_COMMAND = 0x07

# Un télégramme répété (par un module en mode répéteur) arrive peu après l'original.
DUPLICATE_WINDOW = 0.6  # secondes
HISTORY_SIZE = 100  # télégrammes gardés pour les diagnostics


class GatewayError(Exception):
    """Erreur de communication avec la clé."""


class ReComError(GatewayError):
    """Le produit n'a pas répondu ou a refusé une commande Remote Commissioning."""

    def __init__(self, message: str, status: str | None = None) -> None:
        super().__init__(message)
        self.status = status


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

    def __init__(self, port: str, history: deque[dict] | None = None) -> None:
        self.port = port
        self.info: GatewayInfo | None = None
        self._transport: asyncio.Transport | None = None
        self._parser = ESP3Parser()
        self._listeners: dict[int, list[TelegramCallback]] = {}
        self._global_listeners: list[TelegramCallback] = []
        self._response_waiter: asyncio.Future[Packet] | None = None
        self._lock = asyncio.Lock()
        self.on_disconnect: Callable[[], None] | None = None
        # Historique partagé entre rechargements (diagnostics)
        self.history: deque[dict] = history if history is not None else deque(maxlen=HISTORY_SIZE)
        self._record_listeners: list[Callable[[dict], None]] = []
        self.duplicates = 0
        self._recent: dict[tuple[int, int, bytes], float] = {}
        # Remote Management / Remote Commissioning
        self._assembler = recom.SysExAssembler()
        self._reman_listeners: list[ReManCallback] = []
        self._reman_lock = asyncio.Lock()
        self._reman_seq = 0
        self._unlocked: dict[int, float] = {}

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

    async def send_radio(
        self,
        rorg: int,
        payload: bytes,
        sender: int,
        destination: int,
        logged: bytes | None = None,
    ) -> None:
        """Émet un télégramme radio adressé (logged : version masquée pour le journal)."""
        self._record(
            "tx",
            RadioTelegram(
                rorg, bytes(payload if logged is None else logged), sender, destination=destination
            ),
        )
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
            elif packet.packet_type == PACKET_REMOTE_MAN_COMMAND:
                self._on_remote_man_packet(packet)

    def add_record_listener(self, cb: Callable[[dict], None]) -> Callable[[], None]:
        """Abonne cb à chaque télégramme journalisé (émis, reçus, doublons)."""
        self._record_listeners.append(cb)
        return lambda: self._record_listeners.remove(cb)

    def _record(self, direction: str, telegram: RadioTelegram, duplicate: bool = False) -> None:
        self.history.append(
            {
                "time": round(time.time(), 3),
                "dir": direction,
                "sender": telegram.sender_str,
                "destination": id_to_str(telegram.destination),
                "rorg": f"{telegram.rorg:02X}",
                "data": telegram.payload.hex(" ").upper(),
                "status": f"{telegram.status:02X}",
                "dbm": telegram.dbm,
                "duplicate": duplicate,
            }
        )
        for cb in list(self._record_listeners):
            try:
                cb(self.history[-1])
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Erreur dans un écouteur du journal radio")

    def is_duplicate(self, telegram: RadioTelegram) -> bool:
        """Copie répétée d'un télégramme déjà reçu (mode répéteur des modules).

        Les 4 bits de poids faible du statut comptent les répétitions : seule une
        copie répétée (compteur > 0) d'un télégramme identique reçu juste avant
        est ignorée. Deux appuis rapides identiques (compteur 0) sont conservés.
        """
        now = time.monotonic()
        key = (telegram.sender, telegram.rorg, bytes(telegram.payload))
        previous = self._recent.get(key)
        self._recent[key] = now
        if len(self._recent) > 256:
            self._recent = {k: t for k, t in self._recent.items() if now - t < DUPLICATE_WINDOW}
        return (
            telegram.status & 0x0F > 0
            and previous is not None
            and now - previous <= DUPLICATE_WINDOW
        )

    def _dispatch(self, telegram: RadioTelegram) -> None:
        duplicate = self.is_duplicate(telegram)
        self._record("rx", telegram, duplicate)
        _LOGGER.debug(
            "RX %s RORG=%02X data=%s status=%02X dBm=%s%s",
            telegram.sender_str,
            telegram.rorg,
            telegram.payload.hex(" "),
            telegram.status,
            telegram.dbm,
            " (doublon ignoré)" if duplicate else "",
        )
        if duplicate:
            self.duplicates += 1
            return
        if telegram.rorg == recom.RORG_SYS_EX:
            message = self._assembler.feed(
                telegram.sender, telegram.payload, telegram.destination
            )
            if message is not None:
                self._dispatch_reman(message)
            return
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


    # -- Remote Management / Remote Commissioning ---------------------------

    def _on_remote_man_packet(self, packet: Packet) -> None:
        """Message ReMan déjà réassemblé par la clé (ESP3 type 7)."""
        d, opt = packet.data, packet.optional
        if len(d) < 4:
            return
        sender = int.from_bytes(opt[4:8], "big") if len(opt) >= 8 else 0
        destination = int.from_bytes(opt[0:4], "big") if len(opt) >= 4 else 0xFFFFFFFF
        message = recom.ReManMessage(
            function=int.from_bytes(d[0:2], "big") & 0xFFF,
            manufacturer=int.from_bytes(d[2:4], "big") & 0x7FF,
            data=bytes(d[4:]),
            sender=sender,
            destination=destination,
        )
        self.history.append(
            {
                "time": round(time.time(), 3),
                "dir": "rx",
                "sender": id_to_str(sender),
                "destination": id_to_str(destination),
                "rorg": "ReMan",
                "data": f"{message.function:03X} {message.data.hex(' ').upper()}".strip(),
                "status": "",
                "dbm": -opt[8] if len(opt) >= 9 else None,
                "duplicate": False,
            }
        )
        self._dispatch_reman(message)

    def _dispatch_reman(self, message: recom.ReManMessage) -> None:
        _LOGGER.debug(
            "ReMan reçu de %s : fonction %03X, données %s",
            id_to_str(message.sender),
            message.function,
            message.data.hex(" "),
        )
        for cb in list(self._reman_listeners):
            try:
                cb(message)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Erreur dans un écouteur ReMan")

    def subscribe_reman(self, cb: ReManCallback) -> Callable[[], None]:
        self._reman_listeners.append(cb)
        return lambda: self._reman_listeners.remove(cb)

    async def send_reman(
        self, function: int, data: bytes, sender: int, destination: int
    ) -> None:
        """Émet un message ReMan (télégrammes SYS_EX chaînés, adressés)."""
        self._reman_seq = self._reman_seq % 3 + 1
        secret = function in (recom.FN_UNLOCK, recom.FN_LOCK, recom.FN_SET_CODE)
        for chunk in recom.encode_message(function, data, self._reman_seq):
            # Le code de sécurité n'apparaît jamais dans le journal ni les diagnostics.
            logged = chunk[:5] + b"\x00\x00\x00\x00" if secret else None
            await self.send_radio(recom.RORG_SYS_EX, chunk, sender, destination, logged)

    async def reman_request(
        self,
        device_id: int,
        sender: int,
        command: tuple[int, bytes],
        expect: int | None = None,
        timeout: float = 3.0,
        until: Callable[[list[recom.ReManMessage]], bool] | None = None,
        code: int | None = None,
    ) -> list[recom.ReManMessage]:
        """Envoie une commande ReCom et attend la ou les réponses.

        expect : fonction de la réponse attendue (None = acquittement 0x240).
        until : pour les réponses en plusieurs messages, renvoie True quand tout
        est reçu (sinon on rend ce qui est arrivé à l'expiration du délai).
        code : code de sécurité du produit ; il est déverrouillé au besoin. Sans
        code, on compte sur le déverrouillage qui suit sa mise sous tension.
        """
        async with self._reman_lock:
            if code is not None:
                await self._ensure_unlocked(device_id, sender, code)
            try:
                return await self._exchange(
                    device_id, sender, command, expect, timeout, until
                )
            except ReComError:
                # Produit redémarré (reverrouillé) ? On redéverrouillera la prochaine fois.
                self.forget_unlock(device_id)
                raise

    async def _exchange(
        self,
        device_id: int,
        sender: int,
        command: tuple[int, bytes],
        expect: int | None,
        timeout: float,
        until: Callable[[list[recom.ReManMessage]], bool] | None = None,
        check_status: bool = True,
    ) -> list[recom.ReManMessage]:
        function, data = command
        wanted = expect if expect is not None else recom.FN_ACK
        loop = asyncio.get_running_loop()
        received: list[recom.ReManMessage] = []
        done: asyncio.Future[None] = loop.create_future()

        def _cb(message: recom.ReManMessage) -> None:
            if message.sender != device_id or message.function != wanted:
                return
            received.append(message)
            if not done.done() and (until is None or until(received)):
                done.set_result(None)

        unsub = self.subscribe_reman(_cb)
        try:
            await self.send_reman(function, data, sender, device_id)
            try:
                await asyncio.wait_for(asyncio.shield(done), timeout)
            except TimeoutError:
                if not received:
                    status = (
                        await self._query_status(device_id, sender) if check_status else None
                    )
                    if (
                        expect is None
                        and status
                        and status["return_code"] == 0
                        and status["last_function"] == function
                    ):
                        # Commande exécutée, acquittement perdu.
                        return received
                    raise ReComError(
                        f"Pas de réponse ReCom de {id_to_str(device_id)} "
                        f"(fonction {function:03X})",
                        status["status"] if status else None,
                    ) from None
        finally:
            unsub()
        return received

    async def _query_status(self, device_id: int, sender: int) -> dict | None:
        """État de la dernière commande (None si le produit reste muet)."""
        try:
            answer = await self._exchange(
                device_id,
                sender,
                recom.query_status(),
                recom.FN_QUERY_STATUS_ANSWER,
                2.0,
                check_status=False,
            )
        except ReComError:
            return None
        return recom.parse_query_status(answer[0].data)

    async def _ensure_unlocked(self, device_id: int, sender: int, code: int) -> None:
        """Déverrouille le produit si besoin (renouvelé toutes les 10 min)."""
        last = self._unlocked.get(device_id)
        if last is not None and time.monotonic() - last < UNLOCK_RENEW:
            return
        if await self._try(device_id, sender, recom.unlock(code)):
            self._unlocked[device_id] = time.monotonic()
        else:
            _LOGGER.debug("Déverrouillage ReCom de %s sans réponse", id_to_str(device_id))

    async def _try(self, device_id: int, sender: int, command: tuple[int, bytes]) -> bool:
        """Commande acquittée (0x240) ou confirmée par Query Status ?"""
        try:
            await self._exchange(device_id, sender, command, None, 2.0)
        except ReComError:
            return False
        return True

    async def unlock(self, device_id: int, sender: int, code: int) -> bool:
        """Déverrouille le produit avec son code ; True si accepté."""
        async with self._reman_lock:
            ok = await self._try(device_id, sender, recom.unlock(code))
            if ok:
                self._unlocked[device_id] = time.monotonic()
            return ok

    async def set_code(self, device_id: int, sender: int, code: int) -> bool:
        """Attribue un code de sécurité (produit déverrouillé requis) ; True si accepté."""
        async with self._reman_lock:
            ok = await self._try(device_id, sender, recom.set_code(code))
            if ok:
                self._unlocked[device_id] = time.monotonic()
            return ok

    def forget_unlock(self, device_id: int) -> None:
        self._unlocked.pop(device_id, None)


def is_ute(telegram: RadioTelegram) -> UteRequest | None:
    return parse_ute(telegram)
