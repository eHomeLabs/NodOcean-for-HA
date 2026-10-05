# Pont MQTT (NodOcean to MQTT)

Depuis la **v0.5.0**, NodOcean for HA peut envoyer l'état de vos produits NodOn vers un **broker MQTT**, local ou distant, et recevoir des commandes. Le principe est le même que Zigbee2MQTT. Vous pouvez ainsi utiliser vos produits depuis un autre système : Jeedom, Node-RED, un serveur domotique distant, un script…

- Le pont est **facultatif** et **désactivé par défaut**.
- Il **s'ajoute** à l'intégration : les produits restent dans Home Assistant comme avant.
- Si le broker est injoignable, Home Assistant continue de fonctionner. Le pont se reconnecte tout seul.

## Activer le pont

1. **Paramètres → Appareils et services → NodOcean for HA**.
2. Sur la ligne **Clé EnOcean**, cliquez sur **Configurer**.
3. Remplissez les champs, puis **Valider**. La connexion au broker est testée avant l'enregistrement.

| Champ | Rôle |
|---|---|
| Activer le pont MQTT | Marche / arrêt du pont |
| Utiliser le broker de l'intégration MQTT de Home Assistant | Reprend l'adresse, le port et l'identifiant de l'intégration MQTT déjà configurée (add-on Mosquitto par exemple). Les champs du broker sont alors ignorés |
| Adresse du broker | Ex. `192.168.1.20`, `core-mosquitto`, `mqtt.mondomaine.fr` |
| Port | 1883 en général, 8883 en TLS |
| Identifiant / Mot de passe | Facultatifs. Laissez le mot de passe vide pour garder celui déjà enregistré |
| Connexion chiffrée (TLS) | Recommandée pour un broker sur Internet |
| Topic de base | Préfixe de tous les topics, `nodocean` par défaut |
| Nom des produits dans les topics | **Nom du produit** (`nodocean/prise_salon`) ou **ID EnOcean** (`nodocean/0194A3F2`) |

**Options avancées** (repliées) :

| Champ | Rôle |
|---|---|
| Conserver les messages d'état (retain) | Activé par défaut : un client qui se connecte reçoit tout de suite le dernier état |
| QoS | 0, 1 ou 2 |
| Client ID | Vide : `nodocean-<ID de la clé>` |
| Certificat de l'autorité (CA) | Chemin d'un fichier sur Home Assistant (ex. `/ssl/ca.crt`). Vide : certificats du système |
| Ne pas vérifier le certificat du broker | À éviter, sauf pour un certificat auto-signé de test |

> **Nom du produit** : le nom est converti en minuscules sans accents ni espaces (« Prise Salon » → `prise_salon`). Si vous renommez le produit, son topic change. Choisissez **ID EnOcean** pour des topics qui ne changent jamais.

## Topics publiés

| Topic | Contenu | Conservé |
|---|---|---|
| `nodocean/bridge/state` | `online` / `offline` (aussi envoyé par le broker si la connexion est perdue) | oui |
| `nodocean/bridge/info` | Version, ID de la clé, liste des produits et de leurs topics (JSON) | oui |
| `nodocean/<produit>` | État du produit (JSON), à chaque message reçu | selon l'option retain |
| `nodocean/<produit>/availability` | `online` / `offline`, suivant le réglage « Indisponible après » | oui |
| `nodocean/<produit>/action` | Appui de bouton : `left_up`, `single`, `press`… | non |

Exemples d'état :

```json
nodocean/prise_salon        {"state": "ON", "power": 12.5, "energy": 3.214, "rssi": -68, "last_seen": "2026-10-05T10:14:39+00:00", "available": true}
nodocean/capteur_chambre    {"temperature": 19.5, "humidity": 60.0, "rssi": -72, "last_seen": "…", "available": true}
nodocean/volet_cuisine      {"position": 40, "state": "OPEN", "rssi": -60, …}
nodocean/radiateur_bureau   {"mode": "eco", "power": 980.0, "energy": 125.4, …}
```

Champs JSON par produit :

| Produits | Champs |
|---|---|
| SIN-2-1-01, ASP-2, MSP-2 | `state` (ON / OFF), `power` (W) et `energy` (kWh) pour la MSP-2 |
| SIN-2-2-01 | `state_l1`, `state_l2` |
| SIN-2-RS-01 | `position` (0 = fermé, 100 = ouvert), `state` (OPEN / CLOSED) |
| SIN-2-FP-01 | `mode` (`off`, `comfort`, `eco`, `frost_protection`, `comfort_1`, `comfort_2`), `power`, `energy` |
| STP-2, STPH-2 | `temperature` (°C), `humidity` (%), corrections incluses |
| SDO-2, SWO-2 | `open` (true / false) |
| PIR-2 | `motion`, `illuminance` (lx), `voltage` (V) |
| CCS-2 | `card` (true = carte insérée) |
| TSB-2 | `battery` (%) |
| Tous | `rssi` (dBm), `last_seen`, `available` ; modules et prises : `firmware`, `repeater` |

Les boutons (CWS-2-1, CFS-2, CRC-2, TSB-2) publient leurs appuis sur `…/action`. Les valeurs sont les mêmes que dans [Automatisations](Automatisations).

## Commandes

Publiez sur `nodocean/<produit>/set`, en JSON ou en texte simple :

| Produit | JSON | Texte simple |
|---|---|---|
| SIN-2-1-01, ASP-2, MSP-2 | `{"state": "ON"}`, `"OFF"`, `"TOGGLE"` | `ON`, `OFF`, `TOGGLE` |
| SIN-2-2-01 | `{"state_l1": "ON", "state_l2": "OFF"}` | — |
| SIN-2-RS-01 | `{"position": 50}`, `{"state": "OPEN"}`, `"CLOSE"`, `"STOP"` | `OPEN`, `CLOSE`, `STOP`, `50` |
| SIN-2-FP-01 | `{"mode": "eco"}` | `eco` |

- Publiez sur `nodocean/<produit>/get` (contenu quelconque) pour relire l'état d'un module ou d'une prise.
- Les capteurs ne reçoivent pas de commandes : un message sur leur `/set` est ignoré.
- Une commande reçue par MQTT met aussi à jour l'entité dans Home Assistant, et inversement.

Exemple avec `mosquitto_pub` :

```bash
mosquitto_pub -h 192.168.1.20 -u nodon -P motdepasse -t nodocean/prise_salon/set -m '{"state":"ON"}'
mosquitto_sub -h 192.168.1.20 -u nodon -P motdepasse -t 'nodocean/#' -v
```

## Dépannage

- **« Impossible de joindre le broker »** : vérifiez l'adresse, le port, le TLS et le pare-feu. Sur Home Assistant OS avec l'add-on Mosquitto, l'adresse est `core-mosquitto`.
- **« Le broker refuse l'identifiant ou le mot de passe »** : avec l'add-on Mosquitto, utilisez un utilisateur Home Assistant ou un login déclaré dans l'add-on.
- **Alerte « Pont MQTT » dans Corrections** : l'option « Utiliser le broker de l'intégration MQTT » est cochée mais l'intégration MQTT n'existe plus. Ouvrez **Configurer** sur la clé.
- **Diagnostics** : le fichier de diagnostics de la clé contient une partie `mqtt` (connecté ou non, broker, dernière erreur). Le mot de passe y est masqué.
- **Journaux** : les messages du pont commencent par « Pont MQTT ».

## Pas encore disponible

- L'auto-découverte MQTT de Home Assistant (elle ferait apparaître chaque produit en double dans Home Assistant).
- La publication des télégrammes EnOcean bruts.
- Le changement des réglages des produits (LED, répéteur…) par MQTT.
