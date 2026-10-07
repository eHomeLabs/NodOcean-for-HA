# FAQ

**Je ne trouve pas NodOcean for HA en le recherchant dans HACS.**
C'est normal : il n'est pas encore dans le catalogue HACS par défaut (inscription en cours). Ajoutez-le d'abord comme dépôt personnalisé : HACS → **⋮ → Dépôts personnalisés** → `https://github.com/eHomeLabs/NodOcean-for-HA`, type **Intégration**. Voir [Installation](Installation#3-installer-avec-hacs-recommandé).

**Faut-il MQTT, un add-on ou une box EnOcean ?**
Non. Une clé USB EnOcean (USB300 ou compatible ESP3) branchée sur Home Assistant suffit.

**Puis-je garder l'intégration EnOcean native de Home Assistant en parallèle ?**
Non, pas sur la même clé : une clé ne sert qu'à une intégration à la fois. Supprimez l'intégration native (ou utilisez une seconde clé pour elle).

**Mes produits NodOn sont déjà appairés à une autre box. Que faire ?**
Les capteurs et interrupteurs peuvent être appairés à plusieurs récepteurs : ajoutez-les simplement. Pour un module ou une prise, faites l'appairage depuis Home Assistant ; s'il échoue, faites une réinitialisation usine du produit, puis recommencez.

**Mes produits fonctionnent-ils encore en direct, sans Home Assistant ?**
Oui. Un interrupteur NodOn appairé en direct à un module continue de le piloter. Home Assistant voit les deux produits et remonte le nouvel état du module.

**Que se passe-t-il si je change de clé USB ?**
Utilisez **Reconfigurer** sur la ligne de la clé (voir [Configuration de la clé](Configuration-de-la-clé#changer-de-port-ou-de-clé-reconfigurer)). Tous les produits restent dans Home Assistant ; les capteurs et interrupteurs continuent de fonctionner, seuls les modules et prises sont à ré-appairer.

**L'intégration est-elle disponible en anglais ou en allemand ?**
Oui : les écrans suivent la langue de Home Assistant (français, anglais, allemand). La documentation existe aussi [en anglais](English-documentation).

**Les produits sont-ils perdus lors d'une mise à jour de l'intégration ?**
Non. Les produits, leurs noms, pièces et réglages sont conservés.

**Pourquoi Home Assistant n'affiche-t-il pas la vraie valeur d'un réglage ?**
Les produits EnOcean NodOn ne permettent pas de relire leurs réglages. Home Assistant affiche la dernière valeur qu'il a envoyée. Voir [Réglages des produits](Réglages-des-produits#bon-à-savoir).

**Mon produit NodOn n'est pas dans la liste.**
La liste couvre les 16 produits EnOcean NodOn actuels. Pour en demander un autre, ouvrez une [issue](https://github.com/eHomeLabs/NodOcean-for-HA/issues).

**Les produits Zigbee NodOn sont-ils pris en charge ?**
Non, cette intégration est dédiée aux produits EnOcean. Les produits Zigbee NodOn s'intègrent avec ZHA ou Zigbee2MQTT.

**Quelle portée radio ?**
Jusqu'à environ 30 m en intérieur selon les murs. Activez le répéteur d'un module ou d'une prise placé entre la clé et un produit éloigné.

**Comment savoir si la réception est bonne ?**
Activez le capteur **Signal** du produit (carte Diagnostic, entité désactivée par défaut). Au-dessus de −80 dBm, c'est bon ; en dessous de −90 dBm, la liaison est fragile.

**La pile du détecteur de mouvement est-elle surveillée ?**
Oui : le PIR-2 envoie la tension de sa pile CR123A (3 V neuve, environ 5 ans d'autonomie). Une baisse nette et durable de cette tension annonce un remplacement.

**Où trouver la notice d'un produit ?**
Lien **Visiter** sur sa fiche, bouton **Aide NodOn**, ou [support.nodon.fr](https://support.nodon.fr).
