# Configuration de la clé EnOcean

La clé USB est la passerelle radio : elle est déclarée une seule fois, puis tous les produits NodOn s'ajoutent sous elle.

## Ajouter la clé

1. Branchez la clé USB300 sur la machine Home Assistant.
2. Ouvrez **Paramètres → Appareils et services → Ajouter une intégration**, puis cherchez **NodOcean for HA**.
   - Une clé USB300 branchée est souvent détectée automatiquement : une carte **NodOcean for HA** apparaît alors dans **Découvertes**. Cliquez sur **Ajouter**.
3. Choisissez le port de la clé dans la liste. Préférez le chemin `/dev/serial/by-id/usb-EnOcean_GmbH_EnOcean_USB_300_...` : il ne change pas d'un redémarrage à l'autre.
   - Si la clé n'apparaît pas, choisissez **Saisie manuelle** et collez le chemin du port.
4. Validez. L'intégration lit l'identifiant de base de la clé (Base ID) et crée l'appareil **Clé EnOcean**.

La clé apparaît ensuite sous le titre « Clé EnOcean XXXXXXXX » (XXXXXXXX = Base ID).

## Messages d'erreur

| Message | Cause probable | Que faire |
|---|---|---|
| Impossible d'ouvrir le port série | Le port est déjà utilisé par une autre intégration ou un add-on. | Supprimez l'intégration EnOcean native, arrêtez les add-ons EnOcean, puis réessayez. |
| Le port s'ouvre mais la clé ne répond pas | Ce n'est pas une clé EnOcean (adaptateur série générique) ou un add-on parle déjà à la clé. | Vérifiez le nom du port (`EnOcean_GmbH_EnOcean_USB_300…`) et réessayez. |
| L'intégration EnOcean native est active | La clé est réservée par l'intégration EnOcean de Home Assistant. | Supprimez-la d'abord. |
| Cette clé EnOcean est déjà configurée | La clé est déjà déclarée. | Rien à faire, ajoutez directement vos produits. |

## Trouver le chemin de la clé

- **HA OS / Supervised** : **Paramètres → Système → Matériel → ⋮ → Tout le matériel**, puis recherchez « EnOcean ».
- **Container / Core** : `ls -l /dev/serial/by-id/` sur la machine.

## Changer de port ou de clé (Reconfigurer)

Si le chemin de la clé change (autre port USB, passage de `/dev/ttyUSB0` au chemin `by-id`…) ou si vous remplacez la clé :

1. **Paramètres → Appareils et services → NodOcean for HA**.
2. Sur la ligne **Clé EnOcean**, ouvrez le menu **⋮** puis **Reconfigurer**.
3. Choisissez le nouveau port dans la liste, ou tapez son chemin.

<img src="https://raw.githubusercontent.com/eHomeLabs/NodOcean-for-HA/main/docs/images/screenshots/07-menu-cle.png" alt="Menu de la clé : Télécharger les diagnostics, Reconfigurer" width="640">

- **Même clé** : tous les produits sont conservés et continuent de fonctionner.
- **Nouvelle clé** : un écran vous prévient. Les capteurs et interrupteurs continuent de fonctionner. Les modules et prises sont liés à l'ancienne clé : supprimez-les puis ajoutez-les de nouveau.

## Une seule clé

Une seule clé EnOcean est gérée par installation. Tous les produits sont rattachés à cette clé (lien « Connecté via Clé EnOcean » sur leur fiche).

---
Étape suivante : [Ajouter un produit](Ajouter-un-produit)
