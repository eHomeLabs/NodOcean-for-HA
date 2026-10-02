# NodOn EnOcean pour Home Assistant

Intégration Home Assistant **officieuse** dédiée aux produits **EnOcean NodOn**.
Le principe : on choisit son produit dans une liste et Home Assistant fait le reste.
Pas de profil EEP à chercher, pas d'identifiant à recopier, pas de fichier YAML.

[English version below](#english)

## Produits pris en charge

| Produit | Référence | Dans Home Assistant |
|---|---|---|
| Module Multifonction | SIN-2-1-01 | Interrupteur |
| Module Éclairage ON/OFF 2 canaux | SIN-2-2-01 | 2 lumières |
| Module Chauffage Fil Pilote | SIN-2-FP-01 | Sélecteur de mode (6 ordres) + puissance + énergie |
| Module Volet Roulant | SIN-2-RS-01 | Volet avec position |
| Prise intelligente | ASP-2 (ASP-2-1-00 / -10) | Prise |
| Micro Smart Plug + Mesure | MSP-2 (MSP-2-1-01 / -11) | Prise + puissance + énergie |
| Interrupteur mural sans pile | CWS-2-1 | Événements par touche (haut/bas, gauche/droite, combinaisons) |
| Soft Button | TSB-2 | Événements simple / double / long + batterie |
| Détecteur d'ouverture | SDO-2 | Capteur d'ouverture |
| Capteur d'ouverture invisible sans pile | SWO-2 | Capteur d'ouverture |
| Capteur de température | STP-2 | Température |
| Capteur de température et d'humidité | STPH-2 | Température + humidité |

Chaque produit a en plus un capteur « Signal » (RSSI), désactivé par défaut.

## Prérequis

- Home Assistant **2025.3** ou plus récent (toutes les installations : OS, Container, Core).
- Une clé USB EnOcean **USB300**, ou une clé compatible ESP3 (TCM310, USB500…).
- Pas de broker MQTT, pas d'add-on : l'intégration parle directement à la clé.

> ⚠️ Si l'intégration EnOcean native de Home Assistant utilise déjà la clé, supprimez-la d'abord : une clé ne peut servir qu'à une seule intégration à la fois.

## Installation (HACS)

1. Dans HACS, ouvrez **⋮ → Dépôts personnalisés**, ajoutez `https://github.com/eHomeLabs/nodon-enocean-ha` en catégorie **Intégration**.
2. Installez **NodOn EnOcean**, puis redémarrez Home Assistant.
3. **Paramètres → Appareils et services → Ajouter une intégration → NodOn EnOcean**. Une clé USB300 branchée est normalement détectée automatiquement.

Installation manuelle : copiez le dossier `custom_components/nodon_enocean` dans le dossier `config/custom_components/` de Home Assistant, puis redémarrez.

## Ajouter un produit NodOn

1. Ouvrez l'intégration **NodOn EnOcean** et cliquez sur **Ajouter un produit NodOn**.
2. Choisissez le produit dans la liste.
3. Suivez la consigne affichée (par exemple « appuyez 3 fois rapidement sur le bouton du module »), puis cliquez sur **Valider**.
4. Home Assistant écoute pendant 60 s. Il détecte le produit et répond lui-même à sa demande d'appairage pour les modules et les prises.
5. Donnez un nom au produit : c'est terminé.

Pour les capteurs et les interrupteurs, si l'appairage échoue, vous pouvez aussi saisir l'identifiant EnOcean imprimé sur le produit.

### Comment ça marche

- **Modules SIN-2, prises ASP-2 / MSP-2.** Ils envoient une requête *UTE teach-in*, et l'intégration y répond automatiquement. Chaque actionneur reçoit son propre identifiant d'émission : le Base ID de la clé + un décalage de 1 à 127. Les commandes lui sont adressées directement.
- **Capteurs SDO-2 / SWO-2 / STP-2 / STPH-2.** L'intégration détecte leur télégramme d'apprentissage (bit LRN).
- **Interrupteur CWS-2-1.** Le premier appui de touche reçu pendant l'écoute est retenu.
- **Soft Button.** Il est reconnu grâce à sa requête UTE (5 appuis).
- **Interrogation.** Toutes les 60 s, l'intégration demande aux actionneurs leur état, leur puissance et leur énergie.

## Supprimer un produit

Dans la liste des produits de l'intégration, faites **⋮ → Supprimer**. Pensez aussi à effacer l'appairage côté produit si besoin : réinitialisation usine, par exemple un appui de plus de 5 s sur le bouton des modules SIN-2.

## Dépannage

Activez les journaux détaillés dans `configuration.yaml` :

```yaml
logger:
  logs:
    custom_components.nodon_enocean: debug
```

Chaque télégramme reçu est alors journalisé (identifiant, RORG, données, RSSI).

## Développement

```bash
pip install pytest-homeassistant-custom-component pyserial-asyncio-fast
pytest
```

Les tests utilisent un simulateur de clé USB300 (`tests/fake_dongle.py`) et les trames des Quick User Guides NodOn.
La fiche technique de chaque produit (EEP, trames, appairage, sources) est dans [docs/PRODUITS.md](docs/PRODUITS.md).

## Licence

MIT. Projet indépendant : il n'est ni affilié à Home Assistant / Nabu Casa, ni approuvé par eux.

---

## English

Unofficial Home Assistant integration for **NodOn EnOcean** products. Pick your product from a list: Home Assistant handles the EEP profile, the device ID and the pairing response for you.

**Requirements:** Home Assistant 2025.3 or newer and an EnOcean USB300 (or ESP3-compatible) stick. No MQTT needed.

**Install:** add this repository to HACS as a custom repository (category *Integration*), install **NodOn EnOcean**, restart, then add the integration from *Settings → Devices & services*.

**Add a product:** open the integration, click **Add a NodOn product**, choose the model, follow the on-screen pairing instructions and give it a name.

Supported: SIN-2-1-01, SIN-2-2-01, SIN-2-FP-01, SIN-2-RS-01, ASP-2, MSP-2, CWS-2-1, TSB-2, SDO-2, SWO-2, STP-2, STPH-2.
