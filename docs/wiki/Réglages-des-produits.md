# Réglages des produits

Les réglages se trouvent dans la carte **Configuration** de la fiche de chaque produit (**Paramètres → Appareils et services → NodOcean for HA → votre produit**).

## Tableau des réglages

| Réglage | Produits | Valeurs | Effet |
|---|---|---|---|
| **LED de statut** | SIN-2-1-01, SIN-2-2-01, SIN-2-FP-01, ASP-2, MSP-2 | Allumée (mode jour) / éteinte (mode nuit) | Éteint la LED du produit, par exemple dans une chambre. |
| **État après coupure de courant** | SIN-2-1-01, SIN-2-2-01, SIN-2-FP-01, ASP-2, MSP-2 | État précédent / Allumé / Éteint | Comportement du produit au retour du courant. |
| **Bouton local** | SIN-2-1-01, SIN-2-2-01, SIN-2-FP-01, ASP-2, MSP-2 | Actif / inactif | Désactive le bouton du produit et, sur les modules SIN-2, l'interrupteur filaire (seul Home Assistant pilote). |
| **Type d'interrupteur filaire** (v0.7) | SIN-2-1-01, SIN-2-2-01 | Détection automatique / Interrupteur / Interrupteur 2 états / Bouton poussoir | Type d'interrupteur branché sur S1/S2. « 2 états » : contact fermé = allumé, ouvert = éteint (l'état suit la position de l'interrupteur). |
| **Télécommandes appairées en direct** (v0.7) | SIN-2-1-01, SIN-2-2-01 | Actives / ignorées | Ignorées : seules les commandes de Home Assistant (et de la clé) pilotent le module ; les télécommandes appairées directement sont sans effet. |
| **Détection de coupure secteur** | ASP-2, MSP-2 | Active / inactive | Fonction de détection de coupure de la prise. |
| **Extinction automatique** | SIN-2-1-01, SIN-2-2-01 (par canal), ASP-2, MSP-2 | 0 à 3600 s (0 = désactivée) | Éteint la sortie automatiquement après la durée choisie (minuterie). |
| **Extinction radio retardée** | SIN-2-1-01, SIN-2-2-01 (par canal) | 0 à 3600 s | Retarde l'extinction demandée par radio. |
| **Type d'interrupteur filaire** (v0.7) | SIN-2-RS-01 | Type 1 (bistable / tristable) / Type 2 / Type 3 (bistables) / Type 4 (poussoirs) | Réglé par Remote Commissioning. Par défaut le module détecte le type 1 ou 4 au premier appui ; les types 2 et 3 ne se choisissent qu'à distance. Voir la notice du module. |
| **Lancer la calibration / la calibration complète / Arrêter** (v0.7) | SIN-2-RS-01 | Boutons | Calibration classique (haut, bas, haut) ou complète (avec arrêts pour mesurer l'inertie), lancée à distance. L'arrêt rétablit la calibration précédente. |
| **Temps de course** (v0.7) | SIN-2-RS-01 | 5 à 300 s | Remplace la calibration par un temps fixe (montée = descente). **Le module considère alors le volet ouvert (0 %) : mettez-le en haut avant de régler.** |
| **Répéteur EnOcean** | Tous les modules et prises | Désactivé / niveau 1 / niveau 2 | Le produit répète les messages EnOcean pour augmenter la portée (1 ou 2 répétitions). |
| **Remise à zéro de l'énergie** | MSP-2, SIN-2-FP-01 | Bouton | Remet le compteur d'énergie du produit à zéro. |
| **Correction de température** | STP-2, STPH-2 | ± 5 °C | Corrige la mesure affichée (côté Home Assistant). |
| **Correction d'humidité** | STPH-2 | ± 20 % | Idem pour l'humidité. |
| **Indisponible après** | SDO-2, STP-2, STPH-2, PIR-2 | 0 à 1440 min (0 = jamais) | Marque le capteur « indisponible » s'il n'a rien envoyé depuis ce délai (pile vide, hors de portée…). |
| **Façade** | CWS-2-1 | 4 boutons / 2 boutons | En façade 2 boutons, l'interrupteur envoie simplement « Haut » / « Bas ». |

## Bon à savoir

- **Les produits ne renvoient pas leurs réglages.** Home Assistant affiche la dernière valeur envoyée, et la conserve après un redémarrage. Tant que vous n'avez rien changé, les valeurs affichées sont celles d'un produit neuf.
- **Un réglage modifié par une autre box** (ou une réinitialisation usine du produit) n'est pas vu par Home Assistant : renvoyez le réglage depuis Home Assistant.
- **Le répéteur** se règle aussi au produit : 2 appuis brefs sur le bouton des modules SIN-2 passent au niveau suivant (0 → 1 → 2 → 0).
- **Mesures (MSP-2, SIN-2-FP-01)** : l'intégration règle elle-même le rapport automatique. Le produit envoie sa puissance et son énergie au plus tard toutes les 10 min, ou dès 5 W / 10 Wh d'écart.
- **Corrections et « Indisponible après »** n'envoient rien au produit : ce sont des options de Home Assistant.

## Remote Commissioning (v0.7)

Le **Remote Commissioning** (ReCom) est le protocole EnOcean qui permet de lire et modifier à distance la configuration interne d'un produit. L'intégration l'utilise pour les modules SIN-2 et les prises ASP-2 / MSP-2 :

- **Télécommandes appairées** (carte **Diagnostic**) : nombre de télécommandes, interrupteurs ou capteurs appairés **directement** dans le produit (sans Home Assistant). La liste (identifiant, profil EEP, index) est dans les attributs. Appuyez sur **Lire les télécommandes appairées** pour la mettre à jour.
- **Gérer ces télécommandes** : **Paramètres → Appareils et services → NodOcean for HA**, puis sur la ligne du produit **⋮ → Reconfigurer**. Après la lecture du produit (quelques secondes), un menu propose :
  - **Ajouter une télécommande par son identifiant** : appairage direct, sans appuyer sur aucun bouton (identifiant à 8 caractères + type : interrupteur bascule A ou B, interrupteur à carte, poignée, détecteur d'ouverture ou de mouvement, Soft Button) ;
  - **Supprimer des télécommandes appairées** ;
  - **Régler la position atteinte par une télécommande** (volet SIN-2-RS-01 calibré) : bouton (AI, A0, BI, B0, ou carte insérée / retirée) et ouverture en %.
- **Volet SIN-2-RS-01** : le type d'interrupteur, le type de calibration et les temps de montée / descente calibrés sont relus au démarrage (carte **Diagnostic**).

Bon à savoir :

- Le produit doit être alimenté et à portée de la clé. Sans code de sécurité défini (cas des produits NodOn neufs), il accepte le ReCom ; l'intégration envoie le code par défaut `00000000` avant chaque série d'échanges.
- Si le produit ne répond pas, Home Assistant affiche « Le produit n'a pas répondu » : rapprochez-le de la clé ou coupez puis remettez son alimentation, et réessayez.
- Les diagnostics téléchargeables (fiche de la clé) contiennent les derniers échanges ReCom (télégrammes `C5`) pour l'analyse.
