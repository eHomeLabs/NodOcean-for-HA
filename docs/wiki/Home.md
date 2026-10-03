<p align="center"><img src="https://raw.githubusercontent.com/eHomeLabs/NodOcean-for-HA/main/custom_components/nodon_enocean/brand/logo.png" alt="NodOn" height="64"></p>

# NodOcean for HA — documentation

**NodOcean for HA** intègre les produits **EnOcean NodOn** dans Home Assistant. On choisit son produit dans une liste, on suit la consigne affichée, et Home Assistant fait le reste : pas de profil EEP à chercher, pas d'identifiant à recopier, pas de YAML, pas de MQTT.

> Intégration indépendante, non affiliée à Home Assistant / Nabu Casa ni approuvée par eux.

## Par où commencer

| Étape | Page |
|---|---|
| 1. Vérifier le matériel et installer l'intégration | [Installation](Installation) |
| 2. Déclarer la clé USB EnOcean | [Configuration de la clé](Configuration-de-la-clé) |
| 3. Ajouter un premier produit | [Ajouter un produit](Ajouter-un-produit) |
| 4. Retrouver la manipulation d'appairage de chaque produit | [Appairage par produit](Appairage-par-produit) |

## Pour aller plus loin

- [Produits et entités](Produits-et-entités) : ce que chaque produit crée dans Home Assistant.
- [Réglages des produits](Réglages-des-produits) : LED, temporisations, état après coupure, répéteur…
- [Automatisations](Automatisations) : déclencheurs d'appareil des interrupteurs et télécommandes, exemples.
- [Aide et dépannage](Aide-et-dépannage) : bouton Aide NodOn, journaux, erreurs courantes.
- [FAQ](FAQ)
- [Plan de béta-test](Plan-de-béta-test) : les tests à faire pendant la béta.
- **English:** [English documentation](English-documentation)

## Produits pris en charge (16)

<img src="https://raw.githubusercontent.com/eHomeLabs/NodOcean-for-HA/main/docs/images/produits-nodon.png" alt="Les 16 produits NodOn pris en charge" width="600">

| Famille | Produits |
|---|---|
| Modules encastrés | SIN-2-1-01 Multifonction, SIN-2-2-01 Éclairage 2 canaux, SIN-2-FP-01 Fil pilote, SIN-2-RS-01 Volet roulant |
| Prises | ASP-2 Prise intelligente, MSP-2 Micro Smart Plug + mesure |
| Commandes | CWS-2-1 Interrupteur mural, CRC-2 Soft Remote, CFS-2 Interrupteur de sol, CCS-2 Interrupteur à carte, TSB-2 Soft Button |
| Capteurs | SDO-2 Ouverture, SWO-2 Ouverture invisible, PIR-2 Mouvement, STP-2 Température, STPH-2 Température + humidité |

## Liens

- Dépôt et téléchargement : [github.com/eHomeLabs/NodOcean-for-HA](https://github.com/eHomeLabs/NodOcean-for-HA)
- Signaler un problème : [Issues](https://github.com/eHomeLabs/NodOcean-for-HA/issues)
- Notices et support des produits : [support.nodon.fr](https://support.nodon.fr)
