"""Détection des télégrammes d'appairage selon le produit NodOn choisi."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

from .catalog import (
    TEACH_1BS,
    TEACH_4BS,
    TEACH_RPS,
    TEACH_UTE_BIDIR,
    TEACH_UTE_UNI,
    Product,
)
from .eep import is_1bs_teach_in, is_4bs_teach_in, parse_4bs_teach_in_eep
from .esp3 import RORG_RPS, RadioTelegram, UteRequest, parse_ute
from .gateway import Gateway

_LOGGER = logging.getLogger(__name__)

NODON_MANUFACTURER_ID = 0x046


@dataclass
class PairingResult:
    device_id: int
    dbm: int | None
    eep: str
    manufacturer: int | None = None


def match_teach_in(product: Product, telegram: RadioTelegram) -> tuple[bool, UteRequest | None]:
    """Indique si le télégramme est un appairage compatible avec le produit."""
    rorg, func, type_ = product.rorg_func_type
    if product.teach_in in (TEACH_UTE_BIDIR, TEACH_UTE_UNI):
        ute = parse_ute(telegram)
        if ute is None:
            return False, None
        if (ute.rorg, ute.func, ute.type_) != (rorg, func, type_):
            _LOGGER.debug("UTE ignoré (EEP %s attendu %s)", ute.eep, product.eep)
            return False, None
        if ute.request_type == 1:  # demande de suppression explicite
            return False, None
        return True, ute
    if product.teach_in == TEACH_1BS:
        return is_1bs_teach_in(telegram), None
    if product.teach_in == TEACH_4BS:
        if not is_4bs_teach_in(telegram):
            return False, None
        eep = parse_4bs_teach_in_eep(telegram)
        if eep is not None and (eep[0], eep[1]) != (func, type_):
            _LOGGER.debug("Teach-in 4BS ignoré (EEP %s)", eep)
            return False, None
        return True, None
    if product.teach_in == TEACH_RPS:
        return telegram.rorg == RORG_RPS and bool(telegram.payload) and bool(
            telegram.payload[0] & 0x10
        ), None
    return False, None


async def wait_for_teach_in(
    gateway: Gateway,
    product: Product,
    sender_offset: int | None,
    timeout: float,
    exclude: set[int],
) -> PairingResult | None:
    """Attend l'appairage du produit ; répond aux UTE bidirectionnels."""
    loop = asyncio.get_running_loop()
    future: asyncio.Future[PairingResult] = loop.create_future()
    pending_responses: set[asyncio.Task] = set()

    def _on_telegram(telegram: RadioTelegram) -> None:
        if future.done() or telegram.sender in exclude:
            return
        ok, ute = match_teach_in(product, telegram)
        if not ok:
            return
        if product.teach_in == TEACH_UTE_BIDIR and ute is not None:
            assert sender_offset is not None
            sender = gateway.sender_id(sender_offset)

            async def _respond() -> None:
                try:
                    await gateway.send_ute_response(ute, telegram.sender, sender)
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Échec d'envoi de la réponse UTE")

            task = loop.create_task(_respond())
            pending_responses.add(task)
            task.add_done_callback(pending_responses.discard)
        future.set_result(
            PairingResult(
                device_id=telegram.sender,
                dbm=telegram.dbm,
                eep=product.eep,
                manufacturer=ute.manufacturer if ute else None,
            )
        )

    unsubscribe = gateway.subscribe_all(_on_telegram)
    try:
        result = await asyncio.wait_for(future, timeout)
        if pending_responses:
            await asyncio.gather(*pending_responses, return_exceptions=True)
        return result
    except TimeoutError:
        return None
    finally:
        unsubscribe()
