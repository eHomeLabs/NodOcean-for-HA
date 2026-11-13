# NodOcean multimarque — 0.9.0a1

**Vos équipements EnOcean dans Home Assistant, simplement.**

Version expérimentale, branche `develop/multibrand-enocean`, pour le RPi5 Home Assistant de tests. Aucune validation radio matérielle supplémentaire n'est revendiquée.

## Premier périmètre

| Fabricant / parcours | Modèle / EEP | Fonctions | Validation |
|---|---|---|---|
| NodOn | Catalogue existant | Fonctions et réglages existants | Support antérieur conservé ; régression logicielle à vérifier |
| Eltako | FT55, FT4F / F6-02-01 | Événements des touches, relâchement, déclencheurs d'appareil, RSSI | Documentation constructeur ; essai matériel requis |
| EnOcean | EMCSA 868 MHz / D5-00-01 | Ouverture / fermeture, RSSI | Documentation constructeur ; essai matériel requis |
| Generic | F6-02-01 | Événements des touches et déclencheurs d'appareil | Profil seulement ; modèle inconnu |
| Generic | D5-00-01 | Ouverture / fermeture | Profil seulement |
| Generic | A5-02-05 | Température 0 à 40 °C | Profil seulement |
| Generic | A5-04-01 | Humidité ; température si indiquée présente par le télégramme | Profil seulement |

Réception radio non chiffrée seulement pour les nouveaux produits. Aucun actionneur générique, réglage constructeur, ReCom, interrogation ou configuration de rapports automatiques pour les nouveaux produits. Les EEP non proposés ne sont pas pris en charge par ce parcours. Le profil doit être confirmé dans la notice, notamment lorsque l'apprentissage n'annonce pas l'EEP. L'intégration ne déduit pas un fabricant ou un modèle d'un simple appui RPS ou d'une trame 1BS. Le premier produit compatible reçu pendant l'écoute est retenu : n'actionner que le produit voulu et contrôler l'ID à la confirmation.

Les touches sont exposées selon le repérage du profil ; vérifier leur correspondance avec la façade montée. La reconnaissance automatique et les réglages de façade des nouveaux modèles feront l'objet d'évolutions ultérieures.

## Installation de test

1. Réaliser une sauvegarde Home Assistant sur le RPi5 ; utiliser une clé dédiée, compatible avec la fréquence des équipements testés.
2. Télécharger le ZIP de la branche `develop/multibrand-enocean` depuis GitHub (Code → Download ZIP).
3. Copier le dossier `custom_components/nodon_enocean` dans `/config/custom_components/` sur le RPi5, puis redémarrer Home Assistant.
4. Ajouter/configurer NodOcean for HA dans Appareils et services. Le manifeste doit annoncer `0.9.0a1`.
5. Ajouter un équipement : fabricant → modèle, ou Generic → EEP ; lire les limites puis lancer l'écoute et déclencher l'appairage selon les consignes.
6. À la confirmation, vérifier l'ID imprimé sur le produit et choisir nom et pièce.

Cette branche utilise le même domaine technique que la stable : elle la remplace sur l'instance de test. Aucun changement de version stable ni fusion dans `main` n'est réalisé à ce stade.

## Vérifications sur le RPi5

- Eltako : chaque touche, relâchement, combinaisons si prises en charge, déclencheur d'une automatisation.
- Contact : ouverture puis fermeture ; ne pas confondre trame LRN et état.
- Sondes : comparer les mesures à une référence ; A5-02-05 ne convient pas aux autres plages A5-02-xx.
- Activer le RSSI diagnostic et vérifier les mises à jour.
- Recharger l'intégration puis redémarrer HA : mêmes appareils, entités, noms et pièces.
- Vérifier l'absence d'aide NodOn, d'image NodOn et de réglages constructeur sur les nouveaux produits.
- Si MQTT est activé : vérifier états, événements et découverte du fabricant réel sur l'instance distante.
- Pour la régression NodOn : conserver un équipement déjà appairé, ses identifiants d'entités et une automatisation ; vérifier fonctionnement après mise à jour et redémarrage. Les sous-entrées existantes restent lisibles sans migration, les IDs radio et offsets d'émission ne sont pas modifiés.

Consigner version HA, version NodOcean, modèle, firmware si connu, fréquence, EEP, méthode d'apprentissage et résultat. Distinguer simulation et test radio réel.

## Sources constructeur

[Catalogue officiel Eltako 2023](https://www.eltako.com/fileadmin/downloads/en/_main_catalogue/Gesamt-Katalog_gb_lowRes_2023.pdf), tableau des télégrammes : FT55 et FT4F, EEP F6-02-01. Les variantes Bluetooth ou Zigbee ne sont pas concernées.

[Fiche officielle EnOcean EMCSA](https://www.enocean.com/wp-content/uploads/downloads-produkte/en/products/enocean_modules_902mhz/magnet-contact-sensor-emcsu-oem/data-sheet-pdf/EMCS_DataSheet_2020_03.pdf) : version 868 MHz, EEP D5-00-01. Le mode chiffré est exclu de cette première version.

## English

Experimental receive-only multibrand support: Eltako FT55/FT4F (documentation-based, hardware tests pending), plus generic F6-02-01, D5-00-01, A5-02-05 and A5-04-01 profiles. No encrypted radio, generic actuators or vendor-specific settings. Verify the exact EEP and sender ID. Existing `nodon_enocean` model keys, entity/device identifiers and sender offsets remain unchanged. Install only on the dedicated test instance and validate a backed-up existing configuration before production rollout.

## Validation logicielle de cette version

- Python 3.13.18, Home Assistant 2026.2.3, pytest-homeassistant-custom-component 0.13.316.
- Suite complète : **64 tests réussis** (simulateur USB300), dont parcours Eltako/EnOcean, quatre EEP génériques, événements/mesures, rechargement et conservation des identités NodOn et offsets radio.
- Compilation Python et contrôle Ruff F/E9 des fichiers Python modifiés : réussis. Le contrôle global du dépôt signale une double définition préexistante de `ping` dans `recom.py`, hors de ce changement.
- Ces résultats ne constituent ni un test radio réel, ni une validation sur Home Assistant 2026.11. Les vérifications CI HACS/hassfest restent distinctes.
