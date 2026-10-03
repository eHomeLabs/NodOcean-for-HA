# Aide et dépannage

## Le bouton Aide NodOn

Chaque produit a un bouton **Aide NodOn** dans la carte **Diagnostic** de sa fiche.

1. Cliquez sur **Appuyer**.
2. Ouvrez **Notifications** (en bas du menu de gauche de Home Assistant).
3. La notification « Aide NodOn » donne : la notice du produit, le support NodOn (FAQ, notices), le formulaire de contact et l'identifiant EnOcean du produit (à communiquer au support).

<img src="https://raw.githubusercontent.com/eHomeLabs/NodOcean-for-HA/main/docs/images/screenshots/05-aide.png" alt="Aide NodOn : la réponse s'affiche dans Notifications" width="760">

Le lien **Visiter** de la carte « Informations sur l'appareil » ouvre directement la notice du produit.

## Télécharger les diagnostics

Le fichier de diagnostics regroupe la version, la clé, les produits, leurs réglages et les 100 derniers messages radio. C'est la pièce la plus utile pour analyser un problème.

- **Pour toute l'intégration** : Paramètres → Appareils et services → NodOcean for HA → **⋮** de la ligne **Clé EnOcean** → **Télécharger les diagnostics**.
- **Pour un seul produit** : sur la fiche de l'appareil, **⋮** (en haut à droite) → **Télécharger les diagnostics**.

Joignez ce fichier à votre [rapport de bug](https://github.com/eHomeLabs/NodOcean-for-HA/issues/new?template=bug.yml).

## Les alertes dans « Corrections »

En cas de problème avec la clé, une alerte apparaît dans **Paramètres → Système → Corrections** (et une pastille sur Paramètres) :

| Alerte | Que faire |
|---|---|
| **Clé EnOcean injoignable** | Vérifiez que la clé est branchée et qu'aucun add-on ne l'utilise. Si son port a changé, utilisez [Reconfigurer](Configuration-de-la-clé#changer-de-port-ou-de-clé-reconfigurer). |
| **La clé EnOcean est occupée par l'intégration EnOcean native** | Supprimez l'intégration EnOcean native, puis redémarrez Home Assistant. |

L'alerte disparaît d'elle-même dès que la clé répond.

<img src="https://raw.githubusercontent.com/eHomeLabs/NodOcean-for-HA/main/docs/images/screenshots/06-reparation.png" alt="Alerte Clé EnOcean injoignable" width="640">

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
| Un interrupteur déclenche deux fois une automatisation | Depuis la v0.4, les copies envoyées par les modules en mode répéteur sont ignorées automatiquement. Si cela arrive encore, envoyez un fichier de diagnostics. |
| Un module ne répond plus aux commandes | Vérifiez qu'il est alimenté, puis regardez le signal (capteur **Signal** à activer). Au-delà de −90 dBm, rapprochez la clé ou activez le répéteur d'un module intermédiaire. |
| Un capteur reste sur l'ancien état | Les capteurs n'émettent qu'au changement ou toutes les 15 à 30 min. Le SWO-2 n'émet qu'au mouvement. Utilisez le réglage **Indisponible après** pour être prévenu d'un capteur muet. |
| La version firmware affiche « Inconnu » | Le module n'a pas répondu à la demande de version. Ce n'est pas bloquant. Envoyez un journal détaillé si vous voulez qu'on regarde. |
| Le répéteur affiche « inconnu » | Le module n'a pas encore indiqué son niveau. Choisissez un niveau : il sera envoyé et conservé. |
| Le visuel du produit ne s'affiche pas | Home Assistant n'a pas accès à Internet (les visuels sont hébergés sur GitHub). |

## Signaler un problème

Utilisez le formulaire [Signaler un bug](https://github.com/eHomeLabs/NodOcean-for-HA/issues/new?template=bug.yml) : il demande la version, le produit, ce qui se passe et le **fichier de diagnostics**. Pour une idée d'amélioration : [Suggestion](https://github.com/eHomeLabs/NodOcean-for-HA/issues/new?template=feature.yml).

Pour une question sur le produit lui-même (installation électrique, réinitialisation, garantie) : [support.nodon.fr](https://support.nodon.fr).
