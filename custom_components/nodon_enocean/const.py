"""Constantes de l'intégration NodOn EnOcean."""

DOMAIN = "nodon_enocean"
MANUFACTURER = "NodOn"

CONF_DEVICE_PATH = "device"
CONF_MODEL = "model"
CONF_DEVICE_ID = "device_id"
CONF_SENDER_OFFSET = "sender_offset"
CONF_AREA = "area_id"
CONF_NEW_AREA = "new_area"

SUBENTRY_DEVICE = "device"

PAIRING_TIMEOUT = 60  # secondes
POLL_INTERVAL = 60  # secondes, interrogation des actionneurs

EVENT_BUTTON = f"{DOMAIN}_button"  # événement bus pour les déclencheurs d'appareil
