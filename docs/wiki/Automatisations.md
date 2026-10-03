# Automatisations

## Avec l'éditeur (recommandé)

Les interrupteurs et télécommandes proposent des **déclencheurs d'appareil** prêts à l'emploi :

1. **Paramètres → Automatisations et scènes → Créer une automatisation**.
2. **Ajouter un déclencheur → Appareil**, puis choisissez votre interrupteur.
3. Choisissez le déclencheur dans la liste, puis ajoutez vos actions.

Raccourci : sur la fiche de l'appareil, carte **Automatisations**, cliquez sur **+**.

| Produit | Déclencheurs proposés |
|---|---|
| **CWS-2-1** façade 4 boutons | Haut gauche, Bas gauche, Haut droite, Bas droite appuyé ; les 4 combinaisons de 2 touches ; Touche relâchée |
| **CWS-2-1** façade 2 boutons | Haut appuyé, Bas appuyé, Touche relâchée |
| **CRC-2** Soft Remote | Les mêmes que le CWS-2-1 en 4 boutons |
| **CFS-2** Interrupteur de sol | Appui, Touche relâchée |
| **TSB-2** Soft Button | Appui simple, Double appui, Appui long, Fin d'appui long |

La façade du CWS-2-1 se choisit dans ses réglages (carte Configuration → **Façade**).

Pour les autres produits, utilisez les déclencheurs habituels sur leurs entités : « Mouvement détecté » (PIR-2), « Ouvert » (SDO-2, SWO-2), « Carte insérée » (CCS-2), seuil de température, de puissance, etc.

## Exemples en YAML

Remplacez les identifiants d'entités par les vôtres (visibles dans **Paramètres → Entités**).

### Allumer la lumière au passage (PIR-2), l'éteindre 2 min après

```yaml
alias: Couloir - lumière au passage
triggers:
  - trigger: state
    entity_id: binary_sensor.couloir
    to: "on"
actions:
  - action: light.turn_on
    target:
      entity_id: light.couloir
  - wait_for_trigger:
      - trigger: state
        entity_id: binary_sensor.couloir
        to: "off"
        for: "00:02:00"
  - action: light.turn_off
    target:
      entity_id: light.couloir
mode: restart
```

### Interrupteur mural : touche haut gauche = allumer, bas gauche = éteindre

L'entité événement change à chaque appui ; le type d'appui est dans son attribut `event_type`.

```yaml
alias: Salon - interrupteur mural
triggers:
  - trigger: state
    entity_id: event.interrupteur_salon_touches
actions:
  - choose:
      - conditions: "{{ trigger.to_state.attributes.event_type == 'left_up' }}"
        sequence:
          - action: light.turn_on
            target:
              entity_id: light.salon
      - conditions: "{{ trigger.to_state.attributes.event_type == 'left_down' }}"
        sequence:
          - action: light.turn_off
            target:
              entity_id: light.salon
```

Valeurs de `event_type` : `left_up`, `left_down`, `right_up`, `right_down`, `left_up_right_up`, `left_down_right_down`, `left_up_right_down`, `left_down_right_up`, `release` ; en façade 2 boutons : `up`, `down`, `release` ; Soft Button : `single`, `double`, `long`, `long_release` ; interrupteur de sol : `press`, `release`.

### Interrupteur à carte : tout couper quand la carte est retirée

```yaml
alias: Chambre - carte retirée
triggers:
  - trigger: state
    entity_id: binary_sensor.chambre_carte_inseree
    to: "off"
    for: "00:00:30"
actions:
  - action: homeassistant.turn_off
    target:
      area_id: chambre
```

### Fenêtre ouverte : radiateur en hors-gel

```yaml
alias: Bureau - fenêtre ouverte
triggers:
  - trigger: state
    entity_id: binary_sensor.fenetre_bureau
    to: "on"
    for: "00:01:00"
actions:
  - action: select.select_option
    target:
      entity_id: select.radiateur_bureau_mode_fil_pilote
    data:
      option: frost_protection
```

Options du fil pilote : `off`, `comfort`, `comfort_1`, `comfort_2`, `eco`, `frost_protection`.

## Événement technique

Chaque appui envoie aussi un événement `nodon_enocean_button` sur le bus de Home Assistant, avec `device_id` et `type`. Les déclencheurs d'appareil s'appuient dessus ; vous pouvez l'observer dans **Outils de développement → Événements**.
