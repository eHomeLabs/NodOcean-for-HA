# v0.8.4 — ASP avec mesure et Ubiwizz UBID1501S

- Ajout de la prise ASP avec mesure : ASP-2-1-01 (FR), ASP-2-1-11 (DE) et Ubiwizz UBID1501S, profil D2-01-0B.
- Choix distinct de l’ASP-2 sans mesure (ASP-2-1-00 / ASP-2-1-10, D2-01-0A).
- Commande On/Off, retour d’état, puissance et énergie dans Home Assistant et découverte MQTT.
- Conservation du modèle ASP-2 existant et de ses identifiants ; aucune migration requise.
- Après mise à jour et redémarrage de Home Assistant, choisir **Prise intelligente EnOcean avec mesure (Ubiwizz UBID1501S)** pour ajouter cette prise.

Validation : tests automatisés avec la trame UTE signalée, mesures simulées et rechargement. Essai sur la prise réelle encore nécessaire.

## English

Adds the D2-01-0B metering ASP variant (ASP-2-1-01 / ASP-2-1-11 / Ubiwizz UBID1501S), with outlet control, power and energy in Home Assistant and MQTT discovery. The existing D2-01-0A non-metering ASP model and entity identifiers are preserved. After updating and restarting Home Assistant, select the new **EnOcean Metering Smart Plug (Ubiwizz UBID1501S)** entry. Automated simulated tests cover the reported teach-in; hardware validation is pending.
