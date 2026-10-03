"""Réglages disponibles par produit (validés avec l'équipe produit NodOn)."""

from __future__ import annotations

# Réglages locaux D2-01 (CMD 0x2)
LED = frozenset({"SIN-2-1-01", "SIN-2-2-01", "SIN-2-FP-01", "ASP-2", "MSP-2"})
POWER_ON_STATE = LED
LOCAL_CONTROL = frozenset({"SIN-2-FP-01", "ASP-2", "MSP-2"})
POWER_FAILURE = frozenset({"ASP-2", "MSP-2"})

# Temporisations (CMD 0xB)
AUTO_OFF = frozenset({"SIN-2-1-01", "SIN-2-2-01", "ASP-2", "MSP-2"})
DELAY_OFF = frozenset({"SIN-2-1-01", "SIN-2-2-01"})

# Options côté Home Assistant
TEMPERATURE_OFFSET = frozenset({"STP-2", "STPH-2"})
HUMIDITY_OFFSET = frozenset({"STPH-2"})
TIMEOUT = frozenset({"SDO-2", "STP-2", "STPH-2"})
BUTTON_MODE = frozenset({"CWS-2-1"})
