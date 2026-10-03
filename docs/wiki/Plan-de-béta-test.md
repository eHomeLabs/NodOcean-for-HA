# Plan de béta-test

Merci de participer à la béta de **NodOcean for HA** ! Cette page liste les tests à faire. Faites ceux qui concernent **vos** produits : pas besoin de tout tester.

## Avant de commencer

1. Installez la dernière version (voir [Installation](Installation)) et notez son numéro (Paramètres → Appareils et services → NodOcean for HA).
2. Activez les journaux détaillés (voir [Aide et dépannage](Aide-et-dépannage#activer-les-journaux-détaillés)) : ils aideront si un test échoue.
3. Gardez cette page ouverte et notez pour chaque test : **OK**, **KO** ou **non testé**.

## Comment envoyer vos résultats

- **Un test échoue (KO)** : ouvrez un [rapport de bug](https://github.com/eHomeLabs/NodOcean-for-HA/issues/new?template=bug.yml) avec l'identifiant du test (ex. `SIN1-05`) et **joignez le fichier de diagnostics** (⋮ de la clé ou de l'appareil → *Télécharger les diagnostics*).
- **À la fin de vos tests** : envoyez le [retour de béta-test](https://github.com/eHomeLabs/NodOcean-for-HA/issues/new?template=beta.yml) avec vos produits et le bilan.

## Les tests

### Général

| ID | Test | Résultat attendu |
|---|---|---|
| `GEN-01` | Installer NodOcean for HA via HACS, puis redémarrer | L'intégration est proposée dans Ajouter une intégration |
| `GEN-02` | Ajouter la clé (détection automatique ou liste des ports) | Entrée « Clé EnOcean XXXXXXXX » créée |
| `GEN-03` | Avec l'intégration EnOcean native active, ajouter la clé | Message clair : clé occupée par l'intégration native |
| `GEN-04` | Débrancher la clé et redémarrer HA, puis la rebrancher | Correction « Clé EnOcean injoignable » affichée, puis disparaît |
| `GEN-05` | ⋮ de la clé → Reconfigurer → choisir un autre chemin du même port | Produits conservés, tout fonctionne |
| `GEN-06` | ⋮ → Télécharger les diagnostics (intégration et un appareil) | Fichier JSON téléchargé, produits et télégrammes présents |
| `GEN-07` | Mettre à jour depuis une version précédente | Produits, noms, pièces et réglages conservés |
| `GEN-08` | Passer HA en anglais puis en allemand | Écrans d'ajout, entités et notifications traduits |
| `GEN-09` | Ajouter un produit : planche de vignettes, consigne, nom, pièce (existante et nouvelle) | Produit créé dans la bonne pièce |
| `GEN-10` | Échec volontaire d'appairage (ne rien faire 60 s), puis Réessayer | Écran « Aucun produit détecté », puis appairage OK |
| `GEN-11` | Bouton Aide NodOn → Notifications | Notice, support, contact et identifiant EnOcean corrects |
| `GEN-12` | Lien Visiter de la fiche appareil | Ouvre la notice du bon produit |
| `GEN-13` | Redémarrer Home Assistant | États et réglages conservés |

### SIN-2-1-01

| ID | Test | Résultat attendu |
|---|---|---|
| `SIN1-01` | Appairage (3 appuis rapides) | Détecté, LED verte 2 fois |
| `SIN1-02` | Allumer / éteindre depuis HA | Le relais suit, l'état est correct |
| `SIN1-03` | Commande par l'interrupteur filaire ou le bouton local | Nouvel état remonté dans HA (≤ 60 s) |
| `SIN1-04` | LED de statut : éteindre puis rallumer | La LED du module s'éteint / se rallume |
| `SIN1-05` | État après coupure : Éteint, puis couper/rétablir le courant | Le module redémarre éteint |
| `SIN1-06` | Extinction automatique = 10 s, puis allumer | Le module s'éteint seul après 10 s |
| `SIN1-07` | Extinction radio retardée = 10 s, puis éteindre depuis HA | Extinction 10 s plus tard |
| `SIN1-08` | Répéteur niveau 1, puis version firmware | Répéteur accepté ; firmware affiché (ou « Inconnu » à signaler) |

### SIN-2-2-01

| ID | Test | Résultat attendu |
|---|---|---|
| `SIN2-01` | Appairage (3 appuis rapides) | Détecté, 2 lumières créées |
| `SIN2-02` | Canal 1 et canal 2 indépendamment | Chaque sortie suit sa commande |
| `SIN2-03` | Extinction automatique sur le canal 2 seulement | Seul le canal 2 s'éteint seul |
| `SIN2-04` | LED et état après coupure | Comportement conforme au réglage |

### SIN-2-FP-01

| ID | Test | Résultat attendu |
|---|---|---|
| `FP-01` | Appairage (3 appuis en moins de 2 s) | Détecté |
| `FP-02` | Passer par les 6 modes (Arrêt, Confort, -1, -2, Éco, Hors-gel) | Le radiateur suit chaque mode |
| `FP-03` | Puissance et énergie | Valeurs cohérentes, mises à jour seules |
| `FP-04` | Remise à zéro de l'énergie | Énergie repart de 0 |
| `FP-05` | LED, bouton local, état après coupure | À valider : le module applique-t-il ces réglages ? |

### SIN-2-RS-01

| ID | Test | Résultat attendu |
|---|---|---|
| `RS-01` | Appairage puis calibration (5 appuis) | Détecté, volet calibré |
| `RS-02` | Ouvrir, fermer, stop, position 50 % | Le volet suit, position remontée |
| `RS-03` | Commande par l'interrupteur filaire | Position mise à jour dans HA |

### ASP-2

| ID | Test | Résultat attendu |
|---|---|---|
| `ASP-01` | Appairage (appui 2 s, LED rouge) | Détectée, LED verte |
| `ASP-02` | Allumer / éteindre depuis HA et au bouton | État correct dans les deux sens |
| `ASP-03` | Bouton local désactivé | Le bouton de la prise n'agit plus |
| `ASP-04` | LED, état après coupure, extinction automatique | Conforme aux réglages |

### MSP-2

| ID | Test | Résultat attendu |
|---|---|---|
| `MSP-01` | Appairage (appui 2 s, LED rouge) | Détectée |
| `MSP-02` | Puissance avec une charge connue (ex. lampe 60 W) | Valeur proche, mise à jour seule (≤ 10 min ou écart 5 W) |
| `MSP-03` | Énergie dans le tableau de bord Énergie | Consommation visible |
| `MSP-04` | Remise à zéro de l'énergie | Énergie repart de 0 |
| `MSP-05` | Bouton local, LED, état après coupure, extinction auto | Conforme aux réglages |

### CWS-2-1

| ID | Test | Résultat attendu |
|---|---|---|
| `CWS-01` | Appairage (1 appui) | Détecté |
| `CWS-02` | Chaque touche et les combinaisons | Bon événement (haut/bas, gauche/droite) |
| `CWS-03` | Automatisation avec un déclencheur d'appareil | L'automatisation se déclenche une seule fois |
| `CWS-04` | Avec un module en répéteur à proximité | Pas de double déclenchement |
| `CWS-05` | Façade 2 boutons | Événements Haut / Bas |

### CRC-2

| ID | Test | Résultat attendu |
|---|---|---|
| `CRC-01` | Appairage (1 appui) | Détectée |
| `CRC-02` | Chaque bouton : haut gauche, bas gauche, haut droite, bas droite | Le nom de l'événement correspond au bouton appuyé |
| `CRC-03` | Déclencheur d'appareil | OK |

### CFS-2

| ID | Test | Résultat attendu |
|---|---|---|
| `CFS-01` | Appairage puis appuis | Événements Appui / Relâchement |

### CCS-2

| ID | Test | Résultat attendu |
|---|---|---|
| `CCS-01` | Appairage (insérer une carte) | Détecté |
| `CCS-02` | Insérer / retirer la carte, puis redémarrer HA | Carte insérée oui / non, état conservé |

### TSB-2

| ID | Test | Résultat attendu |
|---|---|---|
| `TSB-01` | Appairage (5 appuis brefs) | Détecté |
| `TSB-02` | Appui simple, double, long | Bons événements, batterie affichée |

### SDO-2

| ID | Test | Résultat attendu |
|---|---|---|
| `SDO-01` | Appairage (1 appui) | Détecté |
| `SDO-02` | Ouvrir / fermer | État correct en quelques secondes |
| `SDO-03` | Indisponible après = 60 min, capteur dans le noir | Passe indisponible si plus de message |

### SWO-2

| ID | Test | Résultat attendu |
|---|---|---|
| `SWO-01` | Appairage (LRN + ressort) | Détecté |
| `SWO-02` | Ouvrir / fermer, puis redémarrer HA | État correct et conservé |

### PIR-2

| ID | Test | Résultat attendu |
|---|---|---|
| `PIR-01` | Appairage (1 appui Pairing) | Détecté |
| `PIR-02` | Mouvement puis absence (temporisation du détecteur) | Mouvement oui puis non |
| `PIR-03` | Luminosité et tension de la pile | Valeurs cohérentes (lx, environ 3 V) |

### STP-2

| ID | Test | Résultat attendu |
|---|---|---|
| `STP-01` | Appairage (1 appui) | Détecté |
| `STP-02` | Comparer à un thermomètre de référence | Écart inférieur à 1 °C (sinon : relever les deux valeurs) |
| `STP-03` | Correction de température +1 °C | Valeur affichée décalée de 1 °C |

### STPH-2

| ID | Test | Résultat attendu |
|---|---|---|
| `STPH-01` | Appairage (1 appui) | Détecté |
| `STPH-02` | Comparer température et humidité à une référence | Écarts < 1 °C et < 5 % |

Merci ! Chaque retour, même « tout est OK », aide à valider l'intégration avant sa publication.
