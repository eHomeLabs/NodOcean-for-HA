# Réglages des produits

Les réglages se trouvent dans la carte **Configuration** de la fiche de chaque produit (**Paramètres → Appareils et services → NodOcean for HA → votre produit**).

## Tableau des réglages

| Réglage | Produits | Valeurs | Effet |
|---|---|---|---|
| **LED de statut** | SIN-2-1-01, SIN-2-2-01, SIN-2-FP-01, ASP-2, MSP-2 | Allumée (mode jour) / éteinte (mode nuit) | Éteint la LED du produit, par exemple dans une chambre. |
| **État après coupure de courant** | SIN-2-1-01, SIN-2-2-01, SIN-2-FP-01, ASP-2, MSP-2 | État précédent / Allumé / Éteint | Comportement du produit au retour du courant. |
| **Bouton local** | SIN-2-FP-01, ASP-2, MSP-2 | Actif / inactif | Désactive le bouton du produit (seul Home Assistant pilote). |
| **Détection de coupure secteur** | ASP-2, MSP-2 | Active / inactive | Fonction de détection de coupure de la prise. |
| **Extinction automatique** | SIN-2-1-01, SIN-2-2-01 (par canal), ASP-2, MSP-2 | 0 à 3600 s (0 = désactivée) | Éteint la sortie automatiquement après la durée choisie (minuterie). |
| **Extinction radio retardée** | SIN-2-1-01, SIN-2-2-01 (par canal) | 0 à 3600 s | Retarde l'extinction demandée par radio. |
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

## Réglages prévus plus tard

- Type d'interrupteur filaire des modules SIN-2 (auto-détection / bistable / monostable). Aujourd'hui, le module détecte le type d'interrupteur tout seul.
- Commande locale et télécommandes appairées en direct des modules SIN-2.
- Volet roulant : type d'interrupteur et lancement de la calibration à distance.
