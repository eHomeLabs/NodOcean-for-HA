"""Objet d'exécution représentant un produit NodOn appairé."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from . import eep, recom
from .catalog import Product
from .esp3 import RORG_MSC, RORG_VLD, RadioTelegram, id_to_str
from .gateway import Gateway, GatewayError, ReComError

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

# --- Remote Commissioning --------------------------------------------------------

# Types de télécommandes ajoutables directement dans la table (EEP, canal)
LINK_TYPES: dict[str, tuple[tuple[int, int, int], int]] = {
    "rocker_a": ((0xF6, 0x02, 0x01), 0x00),
    "rocker_b": ((0xF6, 0x02, 0x01), 0x01),
    "key_card": ((0xF6, 0x04, 0x01), 0xFF),
    "window_handle": ((0xF6, 0x10, 0x00), 0xFF),
    "contact": ((0xD5, 0x00, 0x01), 0xFF),
    "motion": ((0xA5, 0x07, 0x01), 0xFF),
    "soft_button": ((0xD2, 0x03, 0x0A), 0xFF),
}
# EEP acceptées par produit (DDF NodOn)
LINK_TYPES_BY_MODEL = {
    "SIN-2-RS-01": ("rocker_a", "rocker_b", "key_card", "soft_button"),
    "SIN-2-FP-01": ("rocker_a", "rocker_b", "key_card", "contact", "motion", "soft_button"),
}
LINK_TYPES_DEFAULT = tuple(LINK_TYPES)
LINK_PAGE = 8  # entrées demandées par requête « Get Link Table »

# Volet SIN-2-RS-01 : paramètres « appareil » ReCom (guide expert V21)
RS_SWITCH_TYPES = ["type_1", "type_2", "type_3", "type_4"]  # valeurs 1 à 4
RS_CALIBRATION = {"classic": 1, "complex": 2, "stop": 3}
RS_CALIBRATION_TYPES = {1: "classic", 2: "complex"}
RS_TIME_UNIT = 0.02  # s, temps de calibration relus (0x0001 = 20 ms)
# Déclencheur associé à une position (paramètre lié 0) : bouton AI AO BI BO
# d'un interrupteur, ou carte insérée / retirée d'un interrupteur à carte.
RS_TRIGGERS = {"ai": 1, "ao": 2, "bi": 3, "bo": 4, "card_in": 1, "card_out": 0}


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
            "switch_type": "auto",
            "travel_time": 0.0,
        }
        # Format des valeurs ReCom : 0xC056 + valeur (firmwares actuels) ou brut.
        self.recom_gp = True
        # Code de sécurité ReCom attribué par l'intégration (None = pas encore).
        self.recom_code: int | None = None
        self.on_code_change: Callable[[NodOnDevice], None] | None = None
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

    def add_listener(
        self, cb: Callable[[set[str]], None], first: bool = False
    ) -> Callable[[], None]:
        """Abonne cb aux changements. first=True : appelé avant les entités
        (le pont MQTT doit voir l'événement de bouton avant qu'il soit consommé)."""
        if first:
            self._listeners.insert(0, cb)
        else:
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
        self.state[f"output_{channel}"] = on
        self.notify({f"output_{channel}"})

    async def set_pilot_wire(self, mode: str) -> None:
        await self._send(eep.d201_pilot_wire_set(PILOT_WIRE_MODES.index(mode)))
        self.state["pilot_wire_mode"] = PILOT_WIRE_MODES.index(mode)
        self.notify({"pilot_wire_mode"})

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
        # Le bit « 2 états » n'a pas de valeur « inchangé » : on renvoie le type choisi.
        mode, two_state = 0, False
        if self.settings.get("switch_type") == "switch_2_state":
            mode, two_state = eep.SWITCH_TYPES["switch_2_state"]
        await self._send(
            eep.d201_set_ext_interface(
                channel,
                new[f"auto_off_{channel}"],
                new[f"delay_off_{channel}"],
                switch_mode=mode,
                two_state=two_state,
            )
        )
        self.settings.update(new)

    async def set_switch_type(self, option: str) -> None:
        """Type d'entrée filaire (CMD 0xB, appliqué à toutes les entrées)."""
        mode, two_state = eep.SWITCH_TYPES[option]
        await self._send(
            eep.d201_set_ext_interface(
                0,
                self.settings.get("auto_off_0", 0),
                self.settings.get("delay_off_0", 0),
                switch_mode=mode,
                two_state=two_state,
            )
        )
        self.settings["switch_type"] = option

    async def set_travel_time(self, seconds: float) -> None:
        """Temps de course du volet (D2-05 CMD 0x5) ; le module repart de 0 %."""
        await self._send(eep.d205_set_travel_time(seconds))
        self.settings["travel_time"] = max(
            eep.TRAVEL_TIME_MIN, min(eep.TRAVEL_TIME_MAX, float(seconds))
        )
        await asyncio.sleep(0.5)
        await self._send(eep.d205_query())

    # -- Remote Commissioning ------------------------------------------------

    async def recom(
        self,
        command: tuple[int, bytes],
        expect: int | None = None,
        timeout: float = 3.0,
        until=None,
    ) -> list[recom.ReManMessage]:
        if self.sender_offset is None:
            raise GatewayError(f"{self.title} n'est pas un actionneur")
        return await self.gateway.reman_request(
            self.device_id,
            self.gateway.sender_id(self.sender_offset),
            command,
            expect,
            timeout,
            until,
            code=self.recom_code,
        )

    @property
    def recom_secured(self) -> bool:
        return self.recom_code is not None

    async def unlock_recom(self) -> str:
        """Bouton « Déverrouiller » : déverrouille avec le code du produit, ou lui en
        attribue un (code aléatoire) s'il est dans sa fenêtre de 15 min après mise
        sous tension. Renvoie "unlocked" ou "assigned"."""
        if self.sender_offset is None:
            raise GatewayError(f"{self.title} n'est pas un actionneur")
        sender = self.gateway.sender_id(self.sender_offset)
        if self.recom_code is not None and await self.gateway.unlock(
            self.device_id, sender, self.recom_code
        ):
            return "unlocked"
        code = recom.random_code()
        if not await self.gateway.set_code(self.device_id, sender, code):
            # Ping : un produit verrouillé y répond quand même (spécification ReMan).
            if await self.gateway.ping(self.device_id, sender):
                raise ReComError(
                    "Le produit répond mais reste verrouillé : il a déjà un code de "
                    "sécurité (QR code, après 11Z)",
                    "locked",
                )
            raise ReComError(
                "Le produit ne répond à aucune commande Remote Commissioning, "
                "même au test Ping",
                "no_answer",
            )
        self._store_code(code)
        return "assigned"

    def _store_code(self, code: int) -> None:
        self.recom_code = code
        self.state["recom_secured"] = True
        if self.on_code_change is not None:
            self.on_code_change(self)
        self.notify({"recom_secured"})

    async def use_code(self, code: int) -> None:
        """Code de sécurité connu (QR code) : déverrouille le produit et le garde."""
        if self.sender_offset is None:
            raise GatewayError(f"{self.title} n'est pas un actionneur")
        sender = self.gateway.sender_id(self.sender_offset)
        if not await self.gateway.unlock(self.device_id, sender, code):
            raise ReComError("Code refusé ou produit muet", "wrong_code")
        self._store_code(code)

    def _value(self, value: int, size: int = 1) -> bytes:
        return recom.gp_enum(value, size) if self.recom_gp else value.to_bytes(size, "big")

    def _learn_format(self, raw: bytes) -> None:
        """Adopte le format de valeur renvoyé par le produit."""
        if len(raw) >= 3:
            self.recom_gp = raw[:2] == recom.GP_ENUM_PREFIX

    async def read_links(self) -> list[dict]:
        """Lit la table des télécommandes appairées (ReCom)."""
        meta = await self.recom(
            recom.get_link_table_metadata(), recom.FN_LINK_TABLE_METADATA_RESPONSE
        )
        info = recom.parse_link_table_metadata(meta[0].data) or {}
        size = info.get("inbound_max") or 24
        entries: dict[int, recom.LinkEntry] = {}
        for start in range(0, size, LINK_PAGE):
            end = min(start + LINK_PAGE, size) - 1
            wanted = set(range(start, end + 1))

            def _complete(messages, wanted=wanted) -> bool:
                got = {
                    e.index for m in messages for e in recom.parse_link_table(m.data)
                }
                return wanted <= got

            messages = await self.recom(
                recom.get_link_table(start, end),
                recom.FN_LINK_TABLE_RESPONSE,
                timeout=4.0,
                until=_complete,
            )
            for message in messages:
                for entry in recom.parse_link_table(message.data):
                    entries[entry.index] = entry
            if not _complete(messages):
                # Réponse partielle : on ne devine pas les entrées manquantes
                # (une entrée prise pour libre pourrait être écrasée).
                raise ReComError("Table des télécommandes reçue incomplète", "incomplete")
        links = [e.as_dict() for _, e in sorted(entries.items()) if not e.empty]
        self.state["links"] = links
        self.state["links_max"] = size
        self.state["links_free"] = [
            i for i in range(size) if i not in entries or entries[i].empty
        ]
        self.notify({"links"})
        return links

    async def delete_link(self, index: int) -> None:
        await self.recom(recom.delete_link(index))
        await asyncio.sleep(0.3)
        await self.read_links()

    async def add_link(self, device_id: int, link_type: str) -> int:
        """Ajoute une télécommande dans la première entrée libre ; renvoie l'index."""
        eep_tuple, channel = LINK_TYPES[link_type]
        await self.read_links()
        free = self.state.get("links_free") or []
        if not free:
            raise ReComError("Table des télécommandes pleine", "full")
        index = free[0]
        await self.recom(
            recom.set_link_table(
                [recom.link_entry_bytes(index, device_id, eep_tuple, channel)]
            )
        )
        await asyncio.sleep(0.3)
        await self.read_links()
        return index

    # Volet roulant (SIN-2-RS-01)

    async def rs_read_config(self) -> dict:
        """Type d'interrupteur, type et temps de calibration (paramètres 0 à 5)."""
        result: dict = {}
        for start, end in ((0, 0), (1, 1), (2, 3), (4, 5)):
            try:
                answer = await self.recom(
                    recom.get_device_config(start, end),
                    recom.FN_DEVICE_CONFIG_RESPONSE,
                    timeout=3.0,
                )
            except ReComError as err:
                _LOGGER.debug("%s : paramètre ReCom %s illisible : %s", self.title, start, err)
                if err.status is None:  # produit muet : inutile d'insister
                    if not result:
                        raise
                    break
                continue
            params = recom.decode_params(answer[0].data)
            if start in params:
                raw = params[start]
                if start == 0:
                    self._learn_format(raw)
                result[start] = recom.decode_value(raw)
        changes: dict = {}
        if result.get(0) in (1, 2, 3, 4):
            changes["rs_switch_type"] = RS_SWITCH_TYPES[result[0] - 1]
        if 1 in result:
            changes["rs_calibration_type"] = RS_CALIBRATION_TYPES.get(result[1])
        for index, key in ((2, "rs_time_down"), (4, "rs_time_up")):
            value = result.get(index)
            if value is not None:
                changes[key] = (
                    round(value * RS_TIME_UNIT, 2) if 0 < value < 0xFFFF else None
                )
        self.state.update(changes)
        self.notify(set(changes) | {"rs_config"})
        return changes

    async def rs_set_switch_type(self, option: str) -> None:
        value = RS_SWITCH_TYPES.index(option) + 1
        await self.recom(recom.set_device_config([(0, self._value(value))]))
        self.state["rs_switch_type"] = option
        self.notify({"rs_switch_type"})

    async def rs_calibrate(self, kind: str) -> None:
        await self.recom(recom.set_device_config([(1, self._value(RS_CALIBRATION[kind]))]))

    async def rs_set_link_position(self, link_index: int, trigger: str, position: int) -> None:
        """Télécommande du volet : déclencheur et position atteinte.

        Position exprimée comme le module : 0 % = ouvert, 100 % = fermé.
        """
        value = RS_TRIGGERS[trigger]
        position = max(0, min(100, int(position)))
        await self.recom(
            recom.set_link_config(
                link_index, [(0, self._value(value)), (1, self._value(position))]
            )
        )

    async def rs_read_link_position(self, link_index: int) -> dict | None:
        answer = await self.recom(
            recom.get_link_config(link_index, 0, 1), recom.FN_LINK_CONFIG_RESPONSE
        )
        parsed = recom.parse_link_config(answer[0].data)
        if parsed is None:
            return None
        _, params = parsed
        out: dict = {}
        if 0 in params:
            self._learn_format(params[0])
            out["button"] = recom.decode_value(params[0])
        if 1 in params:
            out["position"] = recom.decode_value(params[1])
        return out

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
