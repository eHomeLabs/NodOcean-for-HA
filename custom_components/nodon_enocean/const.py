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

# Pont MQTT (options de la clé)
CONF_MQTT_ENABLED = "mqtt_enabled"
CONF_MQTT_USE_HA = "mqtt_use_ha"
CONF_MQTT_HOST = "mqtt_host"
CONF_MQTT_PORT = "mqtt_port"
CONF_MQTT_USERNAME = "mqtt_username"
CONF_MQTT_PASSWORD = "mqtt_password"
CONF_MQTT_TLS = "mqtt_tls"
CONF_MQTT_BASE_TOPIC = "mqtt_base_topic"
CONF_MQTT_TOPIC_NAME = "mqtt_topic_name"
CONF_MQTT_ADVANCED = "advanced"
CONF_MQTT_TLS_INSECURE = "mqtt_tls_insecure"
CONF_MQTT_CA = "mqtt_ca"
CONF_MQTT_CLIENT_ID = "mqtt_client_id"
CONF_MQTT_RETAIN = "mqtt_retain"
CONF_MQTT_QOS = "mqtt_qos"
DEFAULT_BASE_TOPIC = "nodocean"
TOPIC_NAME_NAME = "name"
TOPIC_NAME_ID = "id"
