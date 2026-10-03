"""Objet d'exécution représentant un produit NodOn appairé."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from . import eep
from .catalog import Product
from .esp3 import RORG_MSC, RORG_VLD, RadioTelegram, id_to_str
from .gateway import Gateway, GatewayError

_LOGGER = logging.getLogger(__name__)

PILOT_WIRE_MODES = [
    "off",
    "comfort",
    "eco",
    "frost_protection",
    "comfort_1",
    "comfort_2",
]
REPEATER_LEVELS = ["off", "level_1", "level_2"]

# Rapport automatique des mesures, réglé par l'intégration (MSP-2, SIN-2-FP-01)
POWER_REPORT = {"delta": 5, "max_interval": 600, "min_interval": 10}  # W, s, s
ENERGY_REPORT = {"delta": 10, "max_interval": 600, "min_interval": 10}  # Wh, s, s

# Clé spéciale envoyée aux entités pour réévaluer leur disponibilité
AVAILABILITY_KEY = "_availability"


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
        self.last_seen = time.monotonic()
        # Réglages (non relisibles sur le produit : on garde la dernière valeur envoyée).
        self.settings: dict[str, Any] = {
            "led": True,
            "default_state": "previous",
            "power_failure": False,
            "local_control": True,
            "taught_in": True,
            "temperature_offset": 0.0,
            "humidity_offset": 0.0,
            "timeout": 0,  # minutes sans message avant « indisponible » (0 = jamais)
            "buttons": "4",
        }
        for ch in range(product.channels):
            self.settings[f"auto_off_{ch}"] = 0.0
            self.settings[f"delay_off_{ch}"] = 0.0
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

    @property
    def available(self) -> bool:
        timeout = self.settings.get("timeout") or 0
        return not timeout or time.monotonic() - self.last_seen < timeout * 60

    def notify(self, keys: set[str]) -> None:
        for cb in list(self._listeners):
            cb(keys)

    def decode(self, telegram: RadioTelegram) -> dict[str, Any] | None:
        code = self.product.eep
        if telegram.rorg == RORG_MSC:
            return eep.decode_msc(telegram)
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
        model = self.product.model
        if model == "CRC-2":
            return eep.decode_f60201(telegram, eep.SOFT_REMOTE_NAMES)
        if model == "CFS-2":
            return eep.decode_single_button(telegram)
        if code == "F6-02-01":
            return eep.decode_f60201(telegram)
        if code == "F6-04-01":
            return eep.decode_f60401(telegram)
        if code == "A5-07-03":
            return eep.decode_a50703(telegram)
        if code == "D2-03-0A":
            return eep.decode_d2030a(telegram)
        return None

    def _on_telegram(self, telegram: RadioTelegram) -> None:
        self.last_dbm = telegram.dbm
        self.last_seen = time.monotonic()
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
        self.notify(keys | {AVAILABILITY_KEY})

    # -- Commandes -----------------------------------------------------------

    async def _send(self, payload: bytes, rorg: int = RORG_VLD) -> None:
        if self.sender_offset is None:
            raise GatewayError(f"{self.title} n'est pas un actionneur")
        await self.gateway.send_radio(
            rorg,
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

    # -- Réglages -----------------------------------------------------------

    async def apply_local_settings(self, **changes: Any) -> None:
        """Envoie la CMD 0x2 avec tous les réglages locaux (après mise à jour)."""
        new = {**self.settings, **changes}
        await self._send(
            eep.d201_set_local(
                led=new["led"],
                default_state=new["default_state"],
                power_failure=new["power_failure"],
                local_control=new["local_control"],
                taught_in=new["taught_in"],
            )
        )
        self.settings.update(changes)

    async def set_timer(self, channel: int, kind: str, seconds: float) -> None:
        """kind = "auto_off" ou "delay_off" (CMD 0xB, les deux valeurs envoyées)."""
        new = {**self.settings, f"{kind}_{channel}": seconds}
        await self._send(
            eep.d201_set_ext_interface(
                channel, new[f"auto_off_{channel}"], new[f"delay_off_{channel}"]
            )
        )
        self.settings.update(new)

    async def set_repeater(self, option: str) -> None:
        await self._send(eep.msc_set_repeater(REPEATER_LEVELS.index(option)), RORG_MSC)
        self.state["repeater"] = REPEATER_LEVELS.index(option)

    async def query_info(self) -> None:
        """Demande le niveau du répéteur et la version firmware (messages NodOn)."""
        try:
            await self._send(eep.msc_query_repeater(), RORG_MSC)
            await asyncio.sleep(0.2)
            await self._send(eep.msc_query_firmware(), RORG_MSC)
        except GatewayError as err:
            _LOGGER.debug("Infos de %s indisponibles : %s", self.title, err)

    async def configure_reporting(self) -> None:
        """Règle le rapport automatique de puissance et d'énergie."""
        try:
            await self._send(eep.d201_measurement_config(power=True, **POWER_REPORT))
            await asyncio.sleep(0.2)
            await self._send(eep.d201_measurement_config(power=False, **ENERGY_REPORT))
        except GatewayError as err:
            _LOGGER.debug("Réglage des mesures de %s impossible : %s", self.title, err)

    async def reset_energy(self) -> None:
        await self._send(
            eep.d201_measurement_config(power=False, reset=True, **ENERGY_REPORT)
        )
        self.state["energy"] = 0.0
        self.notify({"energy"})
        await asyncio.sleep(0.3)
        await self._send(eep.d201_measurement_query(power=False))

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
