"""Décodage / encodage des profils EEP utilisés par les produits NodOn.

Chaque décodeur reçoit un `RadioTelegram` et renvoie un dict d'états
(clés = « state keys » utilisées par les entités), ou None si le
télégramme n'est pas pertinent. Aucune dépendance Home Assistant.
"""

from __future__ import annotations

from typing import Any

from .esp3 import RORG_1BS, RORG_4BS, RORG_RPS, RORG_VLD, RadioTelegram

# --- Teach-in ------------------------------------------------------------------


def is_1bs_teach_in(t: RadioTelegram) -> bool:
    return t.rorg == RORG_1BS and len(t.payload) == 1 and not t.payload[0] & 0x08


def is_4bs_teach_in(t: RadioTelegram) -> bool:
    return t.rorg == RORG_4BS and len(t.payload) == 4 and not t.payload[3] & 0x08


def parse_4bs_teach_in_eep(t: RadioTelegram) -> tuple[int, int, int] | None:
    """Teach-in 4BS variante 2 : renvoie (func, type, fabricant) si présent."""
    p = t.payload
    if not is_4bs_teach_in(t) or not p[3] & 0x80:  # bit LRN type = EEP inclus
        return None
    func = p[0] >> 2
    type_ = ((p[0] & 0x03) << 5) | (p[1] >> 3)
    manufacturer = ((p[1] & 0x07) << 8) | p[2]
    return func, type_, manufacturer


# --- D2-01-xx : actionneurs on/off (+ mesure) -----------------------------------

D201_ALL_CHANNELS = 0x1E

UNIT_FACTORS = {
    # unité -> (type, facteur vers W ou Wh)
    0: ("energy", 1 / 3600),  # Ws
    1: ("energy", 1.0),  # Wh
    2: ("energy", 1000.0),  # kWh
    3: ("power", 1.0),  # W
    4: ("power", 1000.0),  # kW
}


def d201_set_output(channel: int, on: bool) -> bytes:
    """CMD 0x1 Actuator Set Output."""
    return bytes([0x01, channel & 0x1F, 0x64 if on else 0x00])


def d201_status_query(channel: int = D201_ALL_CHANNELS) -> bytes:
    """CMD 0x3 Actuator Status Query."""
    return bytes([0x03, channel & 0x1F])


def d201_measurement_query(channel: int = 0, power: bool = True) -> bytes:
    """CMD 0x6 Actuator Measurement Query (power=False : énergie)."""
    return bytes([0x06, (0x20 if power else 0x00) | (channel & 0x1F)])


def d201_pilot_wire_set(mode: int) -> bytes:
    """CMD 0x8 Actuator Set Pilot Wire Mode."""
    return bytes([0x08, mode & 0x07])


def d201_pilot_wire_query() -> bytes:
    """CMD 0x9 Actuator Pilot Wire Mode Query."""
    return bytes([0x09])


def decode_d201(t: RadioTelegram, channels: int = 1) -> dict[str, Any] | None:
    """Décode les réponses D2-01 (status 0x4, mesure 0x7, fil pilote 0xA)."""
    p = t.payload
    if t.rorg != RORG_VLD or not p:
        return None
    cmd = p[0] & 0x0F
    if cmd == 0x04 and len(p) >= 3:
        channel = p[1] & 0x1F
        value = p[2] & 0x7F
        is_on = value > 0
        if channels == 1:
            return {"output_0": is_on}
        if channel == D201_ALL_CHANNELS:
            return {f"output_{c}": is_on for c in range(channels)}
        if channel < channels:
            return {f"output_{channel}": is_on}
        return None
    if cmd == 0x07 and len(p) >= 6:
        unit = (p[1] >> 5) & 0x07
        value = int.from_bytes(p[2:6], "big")
        kind_factor = UNIT_FACTORS.get(unit)
        if kind_factor is None:
            return None
        kind, factor = kind_factor
        if kind == "energy":
            return {"energy": round(value * factor / 1000, 3)}  # kWh
        return {"power": round(value * factor, 1)}  # W
    if cmd == 0x0A and len(p) >= 2:
        return {"pilot_wire_mode": p[1] & 0x07}
    return None


# --- D2-05-00 : volets roulants -------------------------------------------------
# Côté appareil : 0 % = ouvert (haut), 100 % = fermé (bas).
# Côté Home Assistant : 100 = ouvert, 0 = fermé.


def d205_go_to(ha_position: int) -> bytes:
    dev = max(0, min(100, 100 - int(ha_position)))
    return bytes([dev, 0x00, 0x00, 0x01])


def d205_stop() -> bytes:
    return bytes([0x02])


def d205_query() -> bytes:
    return bytes([0x03])


def decode_d205(t: RadioTelegram) -> dict[str, Any] | None:
    p = t.payload
    if t.rorg != RORG_VLD or not p:
        return None
    if len(p) == 4 and p[3] & 0x0F == 0x04:
        pos = p[0]
        if pos > 100:  # 127 = position inconnue
            return {"position": None}
        return {"position": 100 - pos}
    return None


# --- D5-00-01 : contact d'ouverture ---------------------------------------------


def decode_d50001(t: RadioTelegram) -> dict[str, Any] | None:
    if t.rorg != RORG_1BS or len(t.payload) != 1:
        return None
    db0 = t.payload[0]
    if not db0 & 0x08:  # télégramme d'apprentissage : pas d'état fiable
        return None
    # CO : 1 = contact fermé. Pour HA, binary_sensor « ouverture » : True = ouvert.
    return {"opening": not bool(db0 & 0x01)}


# --- A5-02-05 : température 0..40 °C --------------------------------------------


def decode_a50205(t: RadioTelegram) -> dict[str, Any] | None:
    if t.rorg != RORG_4BS or len(t.payload) != 4 or not t.payload[3] & 0x08:
        return None
    raw = t.payload[2]
    # Spécification EEP : 255 = 0 °C, 0 = +40 °C (échelle inversée)
    return {"temperature": round(40 - raw * 40 / 255, 1)}


# --- A5-04-01 : température 0..40 °C + humidité ---------------------------------


def decode_a50401(t: RadioTelegram) -> dict[str, Any] | None:
    if t.rorg != RORG_4BS or len(t.payload) != 4 or not t.payload[3] & 0x08:
        return None
    hum_raw, temp_raw, db0 = t.payload[1], t.payload[2], t.payload[3]
    state: dict[str, Any] = {}
    if hum_raw <= 250:
        state["humidity"] = round(hum_raw * 100 / 250, 1)
    if db0 & 0x02 and temp_raw <= 250:  # TSN : capteur de température présent
        state["temperature"] = round(temp_raw * 40 / 250, 1)
    return state or None


# --- F6-02-01 : interrupteur 2 rockers ------------------------------------------
# R1 : 0 = AI (bas gauche), 1 = A0 (haut gauche), 2 = BI (bas droite), 3 = B0 (haut droite)

ROCKER_NAMES = {0: "left_down", 1: "left_up", 2: "right_down", 3: "right_up"}


def decode_f60201(t: RadioTelegram) -> dict[str, Any] | None:
    if t.rorg != RORG_RPS or len(t.payload) != 1:
        return None
    db0 = t.payload[0]
    pressed = bool(db0 & 0x10)
    if not pressed:
        return {"event": "release"}
    if t.status and not t.status & 0x10:
        # NU = 0 : appui de 3 boutons ou plus, non géré
        return None
    first = ROCKER_NAMES[(db0 >> 5) & 0x07 & 0x03]
    if db0 & 0x01:  # seconde action simultanée
        second = ROCKER_NAMES[(db0 >> 1) & 0x03]
        return {"event": "_".join(sorted((first, second)))}
    return {"event": first}


# --- D2-03-0A : Soft Button (appui + batterie) ----------------------------------

SOFT_BUTTON_ACTIONS = {1: "single", 2: "double", 3: "long", 4: "long_release"}


def decode_d2030a(t: RadioTelegram) -> dict[str, Any] | None:
    p = t.payload
    if t.rorg != RORG_VLD or len(p) != 2:
        return None
    state: dict[str, Any] = {}
    if 1 <= p[0] <= 100:
        state["battery"] = p[0]
    action = SOFT_BUTTON_ACTIONS.get(p[1])
    if action:
        state["event"] = action
    return state or None
