# Ajouter un produit NodOn

Chaque produit s'ajoute en 4 écrans, sans rien saisir d'autre que son nom.

## Les étapes

1. **Paramètres → Appareils et services → NodOcean for HA**, puis cliquez sur **Ajouter un produit NodOn**.
2. **Choisissez le produit** dans la liste. La planche de vignettes en haut de la fenêtre aide à reconnaître votre produit et sa référence (imprimée sur le produit ou son emballage).

   <img src="https://raw.githubusercontent.com/eHomeLabs/NodOcean-for-HA/main/docs/images/screenshots/01-choix-produit.png" alt="Choix du produit" width="520">

3. **Lisez la consigne d'appairage** (avec le visuel du produit), cliquez sur **Valider**, puis faites la manipulation sur le produit. Home Assistant écoute pendant **60 secondes**.

   <img src="https://raw.githubusercontent.com/eHomeLabs/NodOcean-for-HA/main/docs/images/screenshots/02-appairage.png" alt="Consigne d'appairage" width="520">

   - Pour les **modules et prises**, Home Assistant répond lui-même à la demande d'appairage : la LED du produit clignote en vert.
   - Pour les **capteurs et interrupteurs**, il suffit que le produit émette son message d'appairage (ou un premier appui).
   - Les manipulations exactes sont dans [Appairage par produit](Appairage-par-produit).

4. **Produit détecté !** Donnez-lui un nom et choisissez sa **pièce** : une pièce existante, ou tapez un nouveau nom (par exemple « Garage ») pour la créer.

   <img src="https://raw.githubusercontent.com/eHomeLabs/NodOcean-for-HA/main/docs/images/screenshots/04-nom-et-piece.png" alt="Nom et pièce" width="520">

C'est terminé : le produit apparaît sous l'intégration, avec ses entités, ses réglages et son visuel.

## Si rien n'est détecté

Au bout de 60 s, un écran **Aucun produit détecté** propose :

- **Réessayer l'appairage** : rapprochez le produit de la clé (moins de 10 m pendant l'appairage), vérifiez qu'il est alimenté (ou exposé à la lumière pour les capteurs solaires), puis refaites la manipulation.
- **Saisir l'identifiant manuellement** (capteurs et interrupteurs uniquement) : tapez l'identifiant EnOcean à 8 caractères imprimé sur le produit ou son emballage (ex. `0512AB34`).

Un produit déjà ajouté est ignoré pendant l'écoute : il ne peut pas être ajouté deux fois.

## Renommer, changer de pièce

Sur la fiche de l'appareil, utilisez le crayon (en haut à droite) pour changer le nom ou la pièce, comme pour tout appareil Home Assistant.

## Supprimer un produit

1. **Paramètres → Appareils et services → NodOcean for HA**, puis **⋮ → Supprimer** sur la ligne du produit.
2. Effacez aussi l'appairage côté produit si vous voulez le réutiliser ailleurs (réinitialisation usine, voir [Appairage par produit](Appairage-par-produit#réinitialisation-usine)).

## Combien de produits ?

- Jusqu'à **127 modules et prises** par clé : chacun reçoit son propre identifiant d'émission (Base ID de la clé + 1 à 127).
- Pas de limite pratique pour les capteurs et interrupteurs.

---
Voir aussi : [Appairage par produit](Appairage-par-produit) · [Produits et entités](Produits-et-entités)
