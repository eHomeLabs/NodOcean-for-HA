# Fiches techniques d'intégration — produits EnOcean NodOn

Sources : Quick User Guides de l'Integration Kit NodOn, notices utilisateur et fiches techniques ([support.nodon.fr](https://support.nodon.fr)), spécification EnOcean EEP 2.6.8.
Fabricant EnOcean NodOn : **0x046**.

## Actionneurs (bidirectionnels, appairage UTE)

À la mise en mode appairage, chaque actionneur émet `A0 <canaux> 46 00 <TYPE> <FUNC> D2`. La passerelle répond `91 <canaux> 46 00 <TYPE> <FUNC> D2`, en télégramme adressé et depuis l'identifiant d'émission qu'elle a attribué à cet actionneur.

| Produit | EEP | Mise en appairage | Commandes utilisées | Retours |
|---|---|---|---|---|
| SIN-2-1-01 Module Multifonction | D2-01-0F | 3 appuis rapides (LED rouge) | `01 00 64` ON, `01 00 00` OFF, `03 1E` état | `04 60 E4` ON / `04 60 80` OFF |
| SIN-2-2-01 Module Éclairage 2 canaux | D2-01-12 | 3 appuis rapides (les 2 canaux en une fois) | `01 0C 64/00` (C = canal), `03 0C` | `04 60 xx` canal 1, `04 61 xx` canal 2 |
| SIN-2-FP-01 Fil Pilote | D2-01-0C | 3 appuis en moins de 2 s | `08 0M` mode (0 Arrêt, 1 Confort, 2 Éco, 3 Hors-gel, 4 Confort-1, 5 Confort-2), `09` lecture, `06 20` / `06 00` mesures | `0A 0M`, `07 …` mesure |
| SIN-2-RS-01 Volet Roulant | D2-05-00 | 3 appuis rapides | `PP 00 00 01` position (0 = haut, 0x64 = bas), `02` stop, `03` lecture | `PP 00 00 04` |
| ASP-2 Smart Plug | D2-01-0A | appui 2 s (LED rouge), requête toutes les 3 s pendant 30 s | `01 00 64/00`, `03 1E` | `04 60 E4/80` |
| MSP-2 Micro Smart Plug + Mesure | D2-01-0E | appui 2 s (LED rouge) | `01 00 64/00`, `03 1E`, `06 20` puissance, `06 00` énergie | `04 61 E4/80`, `07 UC VV VV VV VV` |

**Mesure (CMD 0x7)** : DB5 bits 7-5 = unité (0 Ws, 1 Wh, 2 kWh, 3 W, 4 kW), bits 4-0 = canal ; DB4..DB1 = valeur sur 32 bits.
**Reset usine des modules SIN-2** : appui de plus de 5 s (LED orange), puis un appui bref pour valider.
**Reset usine des prises ASP-2 / MSP-2** : appui de 5 s jusqu'à la LED orange. Sur la MSP, le compteur d'énergie est aussi remis à zéro.

## Capteurs et boutons (émission seule)

| Produit | EEP | Appairage | Décodage |
|---|---|---|---|
| SDO-2 Détecteur d'ouverture | D5-00-01 | 1 appui sur le bouton arrière (teach-in 1BS, LRN = 0) | DB0 `09` fermé, `08` ouvert ; heartbeat 15 à 30 min |
| SWO-2 Ouverture invisible sans pile | D5-00-01 | maintenir LRN et actionner le ressort | `09` fermé, `08` ouvert ; émission uniquement au mouvement, sans heartbeat |
| STP-2 Température | A5-02-05 | 1 appui sur le bouton arrière (teach-in 4BS) | DB1 : 255 → 0 °C … 0 → 40 °C (spécification EEP) |
| STPH-2 Température + humidité | A5-04-01 | 1 appui sur le bouton arrière (teach-in 4BS) | DB2 × 0,4 = % HR ; DB1 × 0,16 = °C |
| CWS-2-1 Interrupteur mural | F6-02-01 | 1 appui sur une touche | `30` haut gauche, `10` bas gauche, `70` haut droite, `50` bas droite, `00` relâchement, combinaisons `35`/`17`/`37`/`15` |
| CRC-2 Soft Remote | F6-02-01 | 1 appui sur un bouton | `50` haut gauche, `70` bas gauche, `10` haut droite, `30` bas droite, `00` relâchement ; combinaisons `35`/`17`/`37`/`15` |
| CFS-2 Interrupteur de sol | F6-02-01 | 1 appui | appui (bit 0x10) / `00` relâchement |
| CCS-2 Interrupteur à carte | F6-04-01 | insertion d'une carte | `30` carte insérée, `00` carte retirée |
| PIR-2 Détecteur de mouvement | A5-07-03 | 1 appui sur le bouton Pairing (teach-in 4BS) | DB3 × 0,02 = tension pile (V) ; DB2/DB1 10 bits = luminosité 0 à 1000 lx ; DB0 bit 7 = mouvement ; émission toutes les 15 à 21 min ou au changement |
| TSB-2 Soft Button | D2-03-0A | 5 appuis brefs (UTE unidirectionnel `60 01 46 00 0A 03 D2`) | `BB YY` : BB = batterie en %, YY 1 simple / 2 double / 3 long / 4 fin d'appui long |

## Points à valider sur produits réels

1. **STP-2, échelle de température.** La Quick User Guide indique `T = DB1 × 0,16`, alors que la spécification A5-02-05 donne une échelle inversée (`T = 40 − DB1 × 40/255`). L'intégration suit la spécification. Il faut vérifier avec une trame captée à une température connue.
2. **Lecture d'état D2-01 (CMD 0x3).** Les docs NodOn donnent `03 01`. L'intégration envoie `03 1E` (« tous les canaux », selon la spécification) aux produits 1 canal, et `03 00` puis `03 01` au SIN-2-2-01.
3. **Commande ON de l'ASP-2.** Les docs donnent `01 00 01`. L'intégration envoie `01 00 64` (toute valeur de 1 à 0x64 signifie ON selon la notice).
4. **Fil pilote.** La réponse de mesure (CMD 0x7) du SIN-2-FP-01 n'est pas documentée. L'intégration la décode comme celle de la MSP-2.
5. **Identifiant d'émission par actionneur.** L'intégration utilise le Base ID de la clé + 1..127, un identifiant par actionneur. Il faut confirmer que l'appairage et le pilotage fonctionnent ainsi sur chaque firmware.
6. **STP-2 / STPH-2, variante du teach-in 4BS.** Si le capteur envoie un teach-in variante 2 (EEP inclus), l'intégration vérifie que l'EEP correspond au produit choisi. Avec la variante 1, le teach-in est accepté sans vérification.
