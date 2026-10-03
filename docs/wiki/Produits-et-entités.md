# Produits et entités

Chaque produit ajouté devient un **appareil** Home Assistant, rattaché à la clé EnOcean et placé dans sa pièce. Sa fiche contient :

- **Contrôles / Capteurs** : ce que fait le produit ;
- **Configuration** : ses [réglages](Réglages-des-produits) ;
- **Diagnostic** : le bouton [Aide NodOn](Aide-et-dépannage#le-bouton-aide-nodon), le visuel du produit, le signal radio (désactivé par défaut) et, pour les modules, la version firmware ;
- le lien **Visiter**, qui ouvre la notice du produit sur support.nodon.fr.

<img src="https://raw.githubusercontent.com/eHomeLabs/NodOcean-for-HA/main/docs/images/screenshots/03-appareil.png" alt="Fiche d'un module" width="640">

## Entités par produit

| Produit | Entités principales | Remarques |
|---|---|---|
| **SIN-2-1-01** Multifonction | Interrupteur | État relu toutes les 60 s |
| **SIN-2-2-01** Éclairage 2 canaux | 2 lumières (Canal 1, Canal 2) | |
| **SIN-2-FP-01** Fil pilote | Liste « Mode fil pilote » (Arrêt, Confort, Confort -1, Confort -2, Éco, Hors-gel), puissance (W), énergie (kWh) | |
| **SIN-2-RS-01** Volet roulant | Volet avec position (0 à 100 %) | Retour de position tous les 10 % |
| **ASP-2** Prise intelligente | Prise | |
| **MSP-2** Micro Smart Plug | Prise, puissance (W), énergie (kWh) | Utilisable dans le tableau de bord Énergie |
| **CWS-2-1** Interrupteur mural | Événement « Touches » (haut / bas, gauche / droite, combinaisons, relâchement) | Façade 2 ou 4 boutons réglable |
| **CRC-2** Soft Remote | Événement « Boutons » (4 boutons et combinaisons) | |
| **CFS-2** Interrupteur de sol | Événement « Interrupteur » (appui, relâchement) | |
| **CCS-2** Interrupteur à carte | Capteur « Carte insérée » (oui / non) | Dernier état conservé au redémarrage |
| **TSB-2** Soft Button | Événement « Bouton » (simple, double, long, fin d'appui long), batterie (%) | |
| **SDO-2** Détecteur d'ouverture | Capteur d'ouverture | Message de vie toutes les 15 à 30 min |
| **SWO-2** Ouverture invisible | Capteur d'ouverture | N'émet qu'au mouvement ; dernier état conservé au redémarrage |
| **PIR-2** Détecteur de mouvement | Mouvement, luminosité (lx), tension de la pile (V) | Message toutes les 15 à 21 min ou au changement |
| **STP-2** Température | Température (°C) | |
| **STPH-2** Température + humidité | Température (°C), humidité (%) | |

Tous les produits ont aussi un capteur **Signal** (RSSI en dBm), désactivé par défaut : activez-le pour vérifier la qualité de réception.

## Les événements des interrupteurs et télécommandes

Les produits sans pile (CWS-2-1, CRC-2, CFS-2) et le Soft Button n'ont pas d'état « allumé / éteint » : ils envoient des **événements**. Dans Home Assistant, l'entité événement affiche le dernier appui et son heure.

Pour s'en servir, utilisez les déclencheurs d'appareil dans les automatisations : voir [Automatisations](Automatisations).

## Interrogation des actionneurs

Toutes les 60 s, l'intégration demande aux modules et aux prises leur état (et leurs mesures pour MSP-2 et SIN-2-FP-01). Un changement fait au bouton local ou depuis une autre commande est donc remonté dans Home Assistant.
