# ReCom : conservation du code / code persistence

## Français

Correctif lié à l’issue #6 : le code candidat est enregistré durablement avant
l’envoi de Set Code. Sans accusé, un déverrouillage avec ce même code est tenté.
Si aucune confirmation ne parvient, le candidat reste conservé après rechargement
et le capteur affiche « Attribution non confirmée ». Une nouvelle tentative
réutilise ce candidat. Un code déjà confirmé n’est jamais remplacé automatiquement
à la suite d’un échec de déverrouillage. Si la sauvegarde échoue, Set Code n’est
pas envoyé. Les anciens codes enregistrés restent compatibles.

L’attribution au démarrage reste active pour les produits sans code enregistré.
Ce changement ne récupère pas les codes perdus par les versions précédentes.
Un Ping réussi ne prouve pas que le code a été attribué ni que le produit est
déverrouillé. Le champ de code connu du parcours ReCom permet de saisir un code
connu ; il ne permet pas de retrouver un code perdu.

Pour valider sur matériel : sauvegarder Home Assistant, améliorer la liaison radio
si nécessaire, éviter les opérations ReCom simultanées depuis deux passerelles,
puis vérifier le statut et les lectures ReCom avant et après rechargement.
Ne pas publier de code ni de fichiers .storage. Pour un ancien code perdu,
vérifier avec le fabricant la procédure de réinitialisation du modèle et ses
conséquences sur les appairages avant toute remise à zéro. La durée exacte de la
fenêtre ReCom et le choix des index Remote Learn doivent être confirmés pour le
modèle et son firmware ; ce correctif ne les modifie pas.

## English

The candidate code is durably saved before Set Code is sent. Missing acknowledgments
trigger an Unlock attempt using the same candidate. If confirmation is still missing,
the candidate survives reloads and the security sensor reports “Assignment unconfirmed”.
Retries reuse that candidate. A confirmed code is never automatically replaced after
an Unlock failure. Storage failure prevents Set Code transmission. Existing saved
codes remain compatible. Startup assignment for devices without a saved code remains enabled.

Previously lost codes cannot be recovered by this fix. Ping alone does not confirm
assignment or unlock. Hardware validation is still required, including reload and
radio-loss cases. Do not share security codes or .storage files. Confirm the exact
factory-reset procedure, ReCom window and Remote Learn indices with the manufacturer.
