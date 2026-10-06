"""Réglages disponibles par produit (validés avec l'équipe produit NodOn)."""

from __future__ import annotations

# Réglages locaux D2-01 (CMD 0x2)
LED = frozenset({"SIN-2-1-01", "SIN-2-2-01", "SIN-2-FP-01", "ASP-2", "MSP-2"})
POWER_ON_STATE = LED
LOCAL_CONTROL = frozenset({"SIN-2-1-01", "SIN-2-2-01", "SIN-2-FP-01", "ASP-2", "MSP-2"})
# Télécommandes appairées en direct actives / ignorées (CMD 0x2)
TAUGHT_IN = frozenset({"SIN-2-1-01", "SIN-2-2-01"})
POWER_FAILURE = frozenset({"ASP-2", "MSP-2"})

# Temporisations (CMD 0xB)
AUTO_OFF = frozenset({"SIN-2-1-01", "SIN-2-2-01", "ASP-2", "MSP-2"})
DELAY_OFF = frozenset({"SIN-2-1-01", "SIN-2-2-01"})
# Type d'entrée filaire (CMD 0xB)
SWITCH_TYPE = frozenset({"SIN-2-1-01", "SIN-2-2-01"})

# Remote Commissioning (ReCom) : table des télécommandes appairées
# MSP-2 retirée (v0.8.0) : firmware 02.00.00 sans réponse ReMan, même au Ping.
RECOM = frozenset(
    {"SIN-2-1-01", "SIN-2-2-01", "SIN-2-FP-01", "SIN-2-RS-01", "ASP-2"}
)
# Volet roulant : type d'interrupteur, calibration (ReCom), temps de course (D2-05)
ROLLER_SHUTTER = frozenset({"SIN-2-RS-01"})

# Options côté Home Assistant
TEMPERATURE_OFFSET = frozenset({"STP-2", "STPH-2"})
HUMIDITY_OFFSET = frozenset({"STPH-2"})
TIMEOUT = frozenset({"SDO-2", "STP-2", "STPH-2", "PIR-2"})
BUTTON_MODE = frozenset({"CWS-2-1"})
