# Aide et dépannage

## Le bouton Aide NodOn

Chaque produit a un bouton **Aide NodOn** dans la carte **Diagnostic** de sa fiche.

1. Cliquez sur **Appuyer**.
2. Ouvrez **Notifications** (en bas du menu de gauche de Home Assistant).
3. La notification « Aide NodOn » donne : la notice du produit, le support NodOn (FAQ, notices), le formulaire de contact et l'identifiant EnOcean du produit (à communiquer au support).

<img src="https://raw.githubusercontent.com/eHomeLabs/NodOcean-for-HA/main/docs/images/screenshots/05-aide.png" alt="Aide NodOn : la réponse s'affiche dans Notifications" width="760">

Le lien **Visiter** de la carte « Informations sur l'appareil » ouvre directement la notice du produit.

## Activer les journaux détaillés

Ajoutez dans `configuration.yaml`, puis redémarrez :

```yaml
logger:
  logs:
    custom_components.nodon_enocean: debug
```

Chaque télégramme reçu est alors journalisé (identifiant, profil, données, signal). Consultez-les dans **Paramètres → Système → Journaux → Afficher les journaux bruts**. Pensez à retirer ces lignes ensuite : le journal grossit vite.

## Problèmes courants

| Symptôme | Que vérifier |
|---|---|
| La clé ne s'ajoute pas (« Impossible d'ouvrir le port série ») | L'intégration EnOcean native ou un add-on EnOcean utilise encore la clé. Voir [Configuration de la clé](Configuration-de-la-clé#messages-derreur). |
| « La clé ne répond pas » | Le port choisi n'est pas une clé EnOcean (adaptateur série générique). Choisissez le port `usb-EnOcean_GmbH_EnOcean_USB_300…`. |
| Produit non détecté à l'appairage | Distance (moins de 10 m), alimentation ou charge solaire, bonne manipulation : voir [Appairage par produit](Appairage-par-produit). Pour un module ou une prise déjà appairé ailleurs, faites une réinitialisation usine. |
| Un module ne répond plus aux commandes | Vérifiez qu'il est alimenté, puis regardez le signal (capteur **Signal** à activer). Au-delà de −90 dBm, rapprochez la clé ou activez le répéteur d'un module intermédiaire. |
| Un capteur reste sur l'ancien état | Les capteurs n'émettent qu'au changement ou toutes les 15 à 30 min. Le SWO-2 n'émet qu'au mouvement. Utilisez le réglage **Indisponible après** pour être prévenu d'un capteur muet. |
| La version firmware affiche « Inconnu » | Le module n'a pas répondu à la demande de version. Ce n'est pas bloquant. Envoyez un journal détaillé si vous voulez qu'on regarde. |
| Le répéteur affiche « inconnu » | Le module n'a pas encore indiqué son niveau. Choisissez un niveau : il sera envoyé et conservé. |
| Le visuel du produit ne s'affiche pas | Home Assistant n'a pas accès à Internet (les visuels sont hébergés sur GitHub). |

## Signaler un problème

Ouvrez une [issue sur GitHub](https://github.com/eHomeLabs/NodOcean-for-HA/issues) avec :

- la version de NodOcean for HA et de Home Assistant ;
- la référence du produit ;
- ce qui se passe et ce qui était attendu ;
- un extrait du journal détaillé (voir plus haut).

Pour une question sur le produit lui-même (installation électrique, réinitialisation, garantie) : [support.nodon.fr](https://support.nodon.fr).
