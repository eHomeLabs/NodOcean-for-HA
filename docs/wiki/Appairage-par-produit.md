# Appairage par produit

Pendant l'ajout d'un produit ([Ajouter un produit](Ajouter-un-produit)), Home Assistant écoute pendant 60 s. Voici la manipulation à faire sur chaque produit. Elle est aussi rappelée à l'écran, avec le visuel du produit.

**Conseil général :** pendant l'appairage, placez le produit à moins de 10 m de la clé USB.

## Modules encastrés

Le module doit être **raccordé et sous tension**. Home Assistant répond automatiquement à sa demande d'appairage.

| Produit | Manipulation | Confirmation |
|---|---|---|
| **SIN-2-1-01** Module Multifonction | **3 appuis rapides** sur le bouton du module | LED rouge qui scintille (30 s), puis 2 clignotements verts |
| **SIN-2-2-01** Module Éclairage 2 canaux | **3 appuis rapides** sur le bouton du module (les 2 canaux sont appairés en une fois) | Idem |
| **SIN-2-FP-01** Module Fil Pilote | **3 appuis rapides en moins de 2 s** | Idem |
| **SIN-2-RS-01** Module Volet Roulant | **3 appuis rapides** sur le bouton du module | Idem |

**Volet roulant :** si ce n'est pas déjà fait, calibrez le volet après l'appairage : **5 appuis brefs** sur le bouton du module (cycle montée / descente / montée). Si le sens est inversé, intervertissez les fils de montée et de descente.

## Prises

| Produit | Manipulation | Confirmation |
|---|---|---|
| **ASP-2** Prise intelligente (ASP-2-1-00 FR / ASP-2-1-10 DE) | Branchez la prise, **maintenez le bouton 2 s** jusqu'à ce que la LED passe au rouge, puis relâchez | La prise émet sa demande toutes les 3 s pendant 30 s ; LED verte une fois appairée |
| **MSP-2** Micro Smart Plug (MSP-2-1-01 FR / MSP-2-1-11 DE) | Idem : **maintien 2 s** jusqu'à la LED rouge | Idem |

## Commandes sans pile

| Produit | Manipulation |
|---|---|
| **CWS-2-1** Interrupteur mural | Appuyez franchement sur **une touche**. Toutes les touches sont ensuite disponibles. |
| **CRC-2** Soft Remote | Appuyez sur **un bouton** de la télécommande. Les 4 boutons sont ensuite disponibles. |
| **CFS-2** Interrupteur de sol | Appuyez sur l'interrupteur (au pied ou à la main). |
| **CCS-2** Interrupteur à carte | **Insérez une carte** dans le support. |
| **TSB-2** Soft Button | **5 appuis brefs** de suite (moins d'une demi-seconde entre chaque). |

## Capteurs

| Produit | Manipulation |
|---|---|
| **SDO-2** Détecteur d'ouverture | **1 appui** sur le bouton d'appairage à l'arrière du capteur. |
| **SWO-2** Capteur d'ouverture invisible | **Maintenez le bouton LRN** enfoncé **et actionnez le ressort** (enfoncez-le ou relâchez-le). Le bouton LRN seul n'émet rien. |
| **PIR-2** Détecteur de mouvement | **1 appui simple** sur le bouton **Pairing**. Ne faites pas d'appui long : il change la temporisation du détecteur. |
| **STP-2** Capteur de température | **1 appui** sur le bouton d'appairage à l'arrière. |
| **STPH-2** Capteur de température et d'humidité | **1 appui** sur le bouton d'appairage à l'arrière. |

**Capteurs solaires (SDO-2, STP-2, STPH-2) :** un capteur neuf peut être déchargé. Exposez-le quelques minutes à la lumière avant l'appairage.

## Réinitialisation usine

À faire si un produit était appairé à une autre box, ou pour le remettre à zéro.

| Produits | Procédure |
|---|---|
| Modules SIN-2 | Appui de plus de **5 s** sur le bouton (LED orange), puis **un appui bref** pour valider. La LED clignote rouge / vert. |
| Prises ASP-2 / MSP-2 | Appui de **5 s** jusqu'à la LED orange. Sur la MSP-2, le compteur d'énergie est aussi remis à zéro. |

Les procédures détaillées sont dans les notices NodOn (lien **Visiter** sur la fiche de chaque produit, ou [support.nodon.fr](https://support.nodon.fr)).

## Notices des produits

| Produit | Notice |
|---|---|
| SIN-2-1-01 | [Notice](https://support.nodon.fr/support/solutions/articles/150000052176) |
| SIN-2-2-01 | [Notice](https://support.nodon.fr/support/solutions/articles/150000052164) |
| SIN-2-FP-01 | [Notice](https://support.nodon.fr/support/solutions/articles/150000052161) |
| SIN-2-RS-01 | [Notice](https://support.nodon.fr/support/solutions/articles/150000052163) |
| ASP-2 | [Notice](https://support.nodon.fr/support/solutions/articles/150000052200) |
| MSP-2 | [Notice](https://support.nodon.fr/support/solutions/articles/150000052208) |
| CWS-2-1 | [Notice](https://support.nodon.fr/support/solutions/articles/150000052269) |
| CRC-2 | [Notice](https://support.nodon.fr/support/solutions/articles/150000052270) |
| CFS-2 | [Notice](https://support.nodon.fr/support/solutions/articles/150000052272) |
| CCS-2 | [Notice](https://support.nodon.fr/support/solutions/articles/150000052274) |
| TSB-2 | [Notice](https://support.nodon.fr/support/solutions/articles/150000052273) |
| SDO-2 | [Notice](https://support.nodon.fr/support/solutions/articles/150000053854) |
| SWO-2 | [Notice](https://support.nodon.fr/support/solutions/articles/150000192084) |
| PIR-2 | [Notice](https://support.nodon.fr/support/solutions/articles/150000053859) |
| STP-2 | [Notice](https://support.nodon.fr/support/solutions/articles/150000053856) |
| STPH-2 | [Notice](https://support.nodon.fr/support/solutions/articles/150000053858) |
