"""Auto-découverte MQTT de Home Assistant pour le pont NodOcean to MQTT.

Utile pour un AUTRE Home Assistant (ou un logiciel compatible) branché sur le même
broker. Sur le Home Assistant qui fait tourner NodOcean for HA, les produits
apparaîtraient en double : l'option est donc désactivée par défaut.

Topic : <préfixe>/<composant>/nodocean_<ID clé>/<ID produit>_<clé>/config
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .device import PILOT_WIRE_MODES
from .event import (
    FLOOR_SWITCH_EVENTS,
    SOFT_BUTTON_EVENTS,
    SOFT_REMOTE_EVENTS,
    WALL_SWITCH_EVENTS,
)

if TYPE_CHECKING:
    from .device import NodOnDevice
    from .mqtt_bridge import MqttBridge

ORIGIN_URL = "https://github.com/eHomeLabs/NodOcean-for-HA"

EVENT_TYPES = {
    "CWS-2-1": WALL_SWITCH_EVENTS,
    "TSB-2": SOFT_BUTTON_EVENTS,
    "CRC-2": SOFT_REMOTE_EVENTS,
    "CFS-2": FLOOR_SWITCH_EVENTS,
}

# Les noms ne sont pas traduisibles par HA en découverte MQTT : FR ou EN selon
# la langue du Home Assistant qui fait tourner NodOcean for HA.
NAMES = {
    "fr": {
        "channel": "Canal {ch}",
        "mode": "Mode fil pilote",
        "card": "Carte insérée",
        "action": "Boutons",
        "rssi": "Signal",
        "voltage": "Tension de la pile",
        "bridge": "Pont MQTT",
        "gateway": "Clé EnOcean",
    },
    "en": {
        "channel": "Channel {ch}",
        "mode": "Pilot wire mode",
        "card": "Card inserted",
        "action": "Buttons",
        "rssi": "Signal",
        "voltage": "Battery voltage",
        "bridge": "MQTT bridge",
        "gateway": "EnOcean stick",
    },
}

# clé JSON -> (device_class, unité, state_class, catégorie). Nom : celui de la device_class.
SENSORS: dict[str, tuple[str, str, str, str | None]] = {
    "power": ("power", "W", "measurement", None),
    "energy": ("energy", "kWh", "total_increasing", None),
    "temperature": ("temperature", "°C", "measurement", None),
    "humidity": ("humidity", "%", "measurement", None),
    "illuminance": ("illuminance", "lx", "measurement", None),
    "voltage": ("voltage", "V", "measurement", "diagnostic"),
    "battery": ("battery", "%", "measurement", "diagnostic"),
}


def _v(key: str, expr: str | None = None) -> str:
    """Modèle Jinja : valeur de la clé JSON, vide si absente (HA ignore alors le message)."""
    return (
        f"{{% if value_json.{key} is defined %}}{{{{ {expr or 'value_json.' + key} }}}}"
        "{% endif %}"
    )
SENSOR_MODELS = {
    "temperature": {"STP-2", "STPH-2"},
    "humidity": {"STPH-2"},
    "illuminance": {"PIR-2"},
    "voltage": {"PIR-2"},
    "battery": {"TSB-2"},
}


def _device_block(bridge: MqttBridge, device: NodOnDevice) -> dict[str, Any]:
    product = device.product
    return {
        "identifiers": [f"nodocean_{device.id_str}"],
        "name": device.title,
        "manufacturer": "NodOn",
        "model": product.references,
        "model_id": product.model,
        "serial_number": device.id_str,
        "via_device": f"nodocean_gateway_{bridge.info.get('gateway', '')}",
    }


def _names(bridge: MqttBridge) -> dict[str, str]:
    return NAMES["fr" if str(bridge.info.get("language", "")).startswith("fr") else "en"]


def device_configs(bridge: MqttBridge, device: NodOnDevice) -> list[tuple[str, str, dict]]:
    """(composant, object_id, configuration) pour un produit."""
    product = device.product
    model = product.model
    eep = product.eep
    topic = bridge.device_topic(device)
    names = _names(bridge)
    base: dict[str, Any] = {
        "device": _device_block(bridge, device),
        "origin": {
            "name": "NodOcean for HA",
            "sw_version": bridge.info.get("version"),
            "support_url": ORIGIN_URL,
        },
        "availability": [
            {"topic": bridge._t("bridge", "state")},
            {"topic": f"{topic}/availability"},
        ],
        "availability_mode": "all",
        "state_topic": topic,
    }
    out: list[tuple[str, str, dict]] = []

    def add(component: str, key: str, cfg: dict[str, Any]) -> None:
        uid = f"nodocean_{device.id_str}_{key}"
        out.append((component, f"{device.id_str}_{key}", {**base, "unique_id": uid, **cfg}))

    cmd = f"{topic}/set"
    if eep.startswith("D2-01") and eep != "D2-01-0C":
        if product.channels > 1:
            for ch in range(1, product.channels + 1):
                add(
                    "light",
                    f"l{ch}",
                    {
                        "name": names["channel"].format(ch=ch),
                        "schema": "template",
                        "command_topic": cmd,
                        "command_on_template": f'{{"state_l{ch}": "ON"}}',
                        "command_off_template": f'{{"state_l{ch}": "OFF"}}',
                        "state_template": _v(f"state_l{ch}", f"value_json.state_l{ch} | lower"),
                    },
                )
        else:
            add(
                "switch",
                "switch",
                {
                    "name": None,
                    "command_topic": cmd,
                    "payload_on": "ON",
                    "payload_off": "OFF",
                    "state_on": "ON",
                    "state_off": "OFF",
                    "value_template": _v("state"),
                    "device_class": "outlet" if model in ("ASP-2", "MSP-2") else "switch",
                },
            )
    if eep == "D2-05-00":
        add(
            "cover",
            "cover",
            {
                "name": None,
                "device_class": "shutter",
                "command_topic": cmd,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "position_topic": topic,
                "position_template": _v("position"),
                "set_position_topic": cmd,
                "set_position_template": '{"position": {{ position }}}',
                "position_open": 100,
                "position_closed": 0,
                "value_template": _v("state", "value_json.state | lower"),
                "state_open": "open",
                "state_closed": "closed",
            },
        )
    if eep == "D2-01-0C":
        add(
            "select",
            "mode",
            {
                "name": names["mode"],
                "command_topic": cmd,
                "command_template": '{"mode": "{{ value }}"}',
                "value_template": _v("mode"),
                "options": PILOT_WIRE_MODES,
            },
        )
    for key, (dclass, unit, sclass, category) in SENSORS.items():
        if key in ("power", "energy"):
            if not product.metering:
                continue
        elif model not in SENSOR_MODELS[key]:
            continue
        cfg: dict[str, Any] = {
            "device_class": dclass,
            "unit_of_measurement": unit,
            "state_class": sclass,
            "value_template": _v(key),
        }
        if key == "voltage":
            cfg["name"] = names["voltage"]
        if category:
            cfg["entity_category"] = category
        add("sensor", key, cfg)
    for key, model_set, dclass, name in (
        ("open", {"SDO-2", "SWO-2"}, "opening", None),
        ("motion", {"PIR-2"}, "motion", None),
        ("card", {"CCS-2"}, None, names["card"]),
    ):
        if model in model_set:
            cfg = {
                "name": name,
                "payload_on": "ON",
                "payload_off": "OFF",
                "value_template": _v(key, f"'ON' if value_json.{key} else 'OFF'"),
            }
            if dclass:
                cfg["device_class"] = dclass
            add("binary_sensor", key, cfg)
    if model in EVENT_TYPES:
        add(
            "event",
            "action",
            {
                "name": names["action"],
                "device_class": "button",
                "state_topic": f"{topic}/action",
                "event_types": EVENT_TYPES[model],
                "value_template": '{"event_type": "{{ value }}"}',
            },
        )
    add(
        "sensor",
        "rssi",
        {
            "name": names["rssi"],
            "device_class": "signal_strength",
            "unit_of_measurement": "dBm",
            "state_class": "measurement",
            "entity_category": "diagnostic",
            "enabled_by_default": False,
            "value_template": _v("rssi"),
        },
    )
    return out


def all_configs(bridge: MqttBridge) -> dict[str, dict]:
    """Topic de configuration -> configuration, pour tous les produits."""
    prefix = bridge.settings.discovery_prefix
    node = bridge.discovery_node
    configs: dict[str, dict] = {}
    names = _names(bridge)
    gateway = bridge.info.get("gateway", "")
    # La clé EnOcean : connectivité du pont (sert aussi de « via_device » aux produits)
    configs[f"{prefix}/binary_sensor/{node}/bridge/config"] = {
        "name": names["bridge"],
        "unique_id": f"nodocean_gateway_{gateway}_bridge",
        "device_class": "connectivity",
        "entity_category": "diagnostic",
        "state_topic": bridge._t("bridge", "state"),
        "payload_on": "online",
        "payload_off": "offline",
        "device": {
            "identifiers": [f"nodocean_gateway_{gateway}"],
            "name": f"{names['gateway']} {gateway}",
            "manufacturer": "EnOcean",
            "model": "USB300",
            "sw_version": bridge.info.get("version"),
        },
        "origin": {"name": "NodOcean for HA", "support_url": ORIGIN_URL},
    }
    for device in bridge.devices.values():
        for component, object_id, cfg in device_configs(bridge, device):
            configs[f"{prefix}/{component}/{node}/{object_id}/config"] = cfg
    return configs
