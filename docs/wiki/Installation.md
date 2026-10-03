# Installation

## 1. Ce qu'il faut

| Élément | Détail |
|---|---|
| Home Assistant | Version **2025.3** ou plus récente. Toutes les installations : HA OS, Supervised, Container, Core. |
| Clé USB EnOcean | **USB300** (recommandée), ou toute clé compatible ESP3 : TCM310, USB500… |
| HACS | Pour l'installation et les mises à jour en un clic (sinon, voir l'installation manuelle). |
| Produits NodOn EnOcean | Voir la [liste des produits pris en charge](Home#produits-pris-en-charge-16). |

Pas besoin de broker MQTT ni d'add-on : l'intégration dialogue directement avec la clé.

> **Attention aux clés USB génériques.** Un adaptateur série USB (FTDI, CH340…) n'est pas une clé EnOcean. Vérifiez que le nom de la clé contient bien « EnOcean » (par exemple `usb-EnOcean_GmbH_EnOcean_USB_300_DB_...`).

## 2. Libérer la clé

Une clé ne peut servir qu'à **une seule** intégration à la fois. Avant d'installer NodOcean for HA :

1. Dans **Paramètres → Appareils et services**, supprimez l'intégration **EnOcean** native de Home Assistant si elle est configurée.
2. Arrêtez les add-ons qui utiliseraient la clé (EnOcean MQTT, EnOceanMQTT UI…).
3. Si Home Assistant propose la clé dans **Découvertes** avec l'intégration EnOcean native, cliquez sur **Ignorer**.

## 3. Installer avec HACS (recommandé)

1. Ouvrez **HACS**, puis **⋮ → Dépôts personnalisés**.
2. Ajoutez l'adresse `https://github.com/eHomeLabs/NodOcean-for-HA`, catégorie **Intégration**.
3. Recherchez **NodOcean for HA** dans HACS et cliquez sur **Télécharger**.
4. **Redémarrez Home Assistant** (Paramètres → Système → Redémarrer).

## 4. Installation manuelle (sans HACS)

1. Téléchargez la [dernière version](https://github.com/eHomeLabs/NodOcean-for-HA/releases/latest) (fichier « Source code (zip) »).
2. Copiez le dossier `custom_components/nodon_enocean` dans le dossier `config/custom_components/` de Home Assistant (créez `custom_components` s'il n'existe pas).
3. Redémarrez Home Assistant.

## 5. Mettre à jour

- **Avec HACS** : une mise à jour apparaît dans **Paramètres → Mises à jour** (ou dans HACS). Installez-la, puis redémarrez Home Assistant.
- **Manuellement** : remplacez le dossier `custom_components/nodon_enocean`, puis redémarrez.

Les produits déjà appairés et leurs réglages sont conservés lors des mises à jour.

## 6. Désinstaller

1. Supprimez l'intégration dans **Paramètres → Appareils et services → NodOcean for HA → ⋮ → Supprimer**.
2. Supprimez-la ensuite dans HACS (ou le dossier `custom_components/nodon_enocean`), puis redémarrez.

---
Étape suivante : [Configuration de la clé](Configuration-de-la-clé)
