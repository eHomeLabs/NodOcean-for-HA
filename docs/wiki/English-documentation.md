# NodOcean for HA — English documentation

**NodOcean for HA** brings **NodOn EnOcean** products into Home Assistant. Pick your product from a list, follow the on-screen pairing step, and Home Assistant does the rest: no EEP profile to look up, no ID to copy, no YAML, no MQTT. The user interface is available in English, French and German (it follows Home Assistant's language).

> Independent project, not affiliated with or endorsed by Home Assistant / Nabu Casa.

<img src="https://raw.githubusercontent.com/eHomeLabs/NodOcean-for-HA/main/docs/images/produits-nodon.png" alt="The 16 supported NodOn products" width="600">

**Contents:** [Installation](#1-installation) · [Stick setup](#2-enocean-stick-setup) · [Adding a product](#3-adding-a-product) · [Pairing per product](#4-pairing-per-product) · [Entities](#5-products-and-entities) · [Settings](#6-product-settings) · [Automations](#7-automations) · [Help and troubleshooting](#8-help-and-troubleshooting) · [FAQ](#9-faq)

## 1. Installation

| Requirement | Details |
|---|---|
| Home Assistant | **2025.3** or newer, any installation type (OS, Supervised, Container, Core). |
| EnOcean USB stick | **USB300** (recommended) or any ESP3-compatible stick (TCM310, USB500…). A generic USB-serial adapter (FTDI, CH340) is not an EnOcean stick. |
| HACS | For one-click install and updates (manual install also possible). |

**Free the stick first.** A stick can only serve one integration. Remove Home Assistant's native **EnOcean** integration and stop any EnOcean add-on. If Home Assistant offers the stick under **Discovered** for the native integration, click **Ignore**.

**With HACS:**
1. HACS → **⋮ → Custom repositories** → add `https://github.com/eHomeLabs/NodOcean-for-HA`, category **Integration**.
2. Search **NodOcean for HA**, click **Download**, then **restart Home Assistant**.

**Manually:** copy `custom_components/nodon_enocean` from the [latest release](https://github.com/eHomeLabs/NodOcean-for-HA/releases/latest) into `config/custom_components/`, then restart.

**Updates** appear in **Settings → Updates** (or HACS). Paired products, names, areas and settings are kept.

## 2. EnOcean stick setup

1. Plug the USB300 stick in.
2. **Settings → Devices & services → Add integration → NodOcean for HA** (a plugged-in USB300 is often discovered automatically: click **Add**).
3. Pick the stick's port. Prefer `/dev/serial/by-id/usb-EnOcean_GmbH_EnOcean_USB_300_...`: it never changes. Use **manual entry** if it is not listed.

| Message | Meaning |
|---|---|
| Cannot open the serial port | Another integration or add-on is using the stick. |
| The stick does not answer | The port is not an EnOcean stick, or an add-on talks to it. |
| The native EnOcean integration is active | Remove it first. |

**Change port or stick (Reconfigure):** on the **EnOcean stick** row, open **⋮ → Reconfigure** and pick the new port. Same stick: everything keeps working. New stick: sensors and switches keep working; relay modules and plugs are bound to the old stick and must be removed and added again.

## 3. Adding a product

1. **Settings → Devices & services → NodOcean for HA → Add a NodOn product**.
2. Choose the product (the picture board at the top helps you recognise it and its reference).
3. Read the pairing instructions, click **Submit**, then do the pairing step on the product. Home Assistant listens for **60 seconds**; for relay modules and plugs it answers the pairing request itself.
4. **Product detected!** Give it a name and pick an area (existing, or type a new name to create it).

If nothing is detected: **Retry pairing** (closer than 10 m, product powered or solar sensor charged), or for sensors and switches **Enter the ID manually** (8-character EnOcean ID printed on the product).

To remove a product: **⋮ → Delete** on its row. Up to 127 relay modules and plugs per stick.

## 4. Pairing per product

| Product | Pairing step |
|---|---|
| **SIN-2-1-01** Multifunction relay switch | Module powered: **3 quick presses** on its button (LED flickers red, then blinks green twice). |
| **SIN-2-2-01** 2-channel lighting relay | **3 quick presses** (both channels paired at once). |
| **SIN-2-FP-01** Pilot wire heating module | **3 presses within 2 s**. |
| **SIN-2-RS-01** Roller shutter module | **3 quick presses**. Then calibrate if needed: 5 short presses (up/down/up cycle). |
| **ASP-2** Smart plug (ASP-2-1-00 FR / ASP-2-1-10 DE) | Plug in, **hold the button 2 s** until the LED turns red, release. |
| **MSP-2** Micro smart plug + metering (MSP-2-1-01 FR / MSP-2-1-11 DE) | Same: **hold 2 s** until the LED turns red. |
| **CWS-2-1** Wall switch | Press **any key** firmly. |
| **CRC-2** Soft Remote | Press **any button**. |
| **CFS-2** Floor switch | Press the switch (foot or hand). |
| **CCS-2** Card switch | **Insert a card**. |
| **TSB-2** Soft Button | **5 short presses** in a row. |
| **SDO-2** Door/window sensor | **1 press** on the pairing button at the back (expose a new sensor to light first). |
| **SWO-2** Invisible opening sensor | **Hold LRN and actuate the spring**. |
| **PIR-2** Motion sensor | **1 short press** on **Pairing** (a 3 s press changes the time-out). |
| **STP-2** / **STPH-2** Temperature (+ humidity) | **1 press** on the pairing button at the back. |

Factory reset: SIN-2 modules, press **> 5 s** (orange LED) then a short press; ASP-2 / MSP-2, press **5 s** until orange. User guides: **Visit** link on each device page, or [support.nodon.fr](https://support.nodon.fr).

## 5. Products and entities

| Product | Main entities |
|---|---|
| SIN-2-1-01 | Switch |
| SIN-2-2-01 | 2 lights |
| SIN-2-FP-01 | Pilot wire mode select (Off, Comfort, Comfort -1, Comfort -2, Eco, Frost protection), power, energy |
| SIN-2-RS-01 | Cover with position |
| ASP-2 | Outlet |
| MSP-2 | Outlet, power, energy (Energy dashboard ready) |
| CWS-2-1 / CRC-2 | Button event (keys and combinations) |
| CFS-2 | Event (press, release) |
| CCS-2 | Card inserted (on/off) |
| TSB-2 | Event (single, double, long, long release), battery |
| SDO-2 / SWO-2 | Opening sensor |
| PIR-2 | Motion, illuminance (lx), battery voltage |
| STP-2 / STPH-2 | Temperature (+ humidity) |

Every device page also has a **Diagnostic** card (NodOn help button, product picture, firmware version for modules, **Signal** RSSI sensor disabled by default) and a **Visit** link to the product user guide. Relay modules and plugs are polled every 60 s.

## 6. Product settings

Settings are in the **Configuration** card of each device page.

| Setting | Products | Values |
|---|---|---|
| Status LED (day/night mode) | SIN-2-1-01, SIN-2-2-01, SIN-2-FP-01, ASP-2, MSP-2 | On / off |
| State after power failure | same | Previous / on / off |
| Local button | SIN-2-FP-01, ASP-2, MSP-2 | Enabled / disabled |
| Power failure detection | ASP-2, MSP-2 | Enabled / disabled |
| Auto off timer | SIN-2-1-01, SIN-2-2-01 (per channel), ASP-2, MSP-2 | 0–3600 s (0 = off) |
| Delayed radio off | SIN-2-1-01, SIN-2-2-01 (per channel) | 0–3600 s |
| EnOcean repeater | all relay modules and plugs | Off / level 1 / level 2 |
| Reset energy | MSP-2, SIN-2-FP-01 | Button |
| Temperature / humidity offset | STP-2, STPH-2 | ±5 °C / ±20 % |
| Unavailable after | SDO-2, STP-2, STPH-2, PIR-2 | 0–1440 min without a message (0 = never) |
| Faceplate | CWS-2-1 | 4 buttons / 2 buttons |

Products cannot report their settings back: Home Assistant shows the last value it sent and restores it after a restart. Metering reports (MSP-2, SIN-2-FP-01) are set up automatically: every 10 min at the latest, or on a 5 W / 10 Wh change.

## 7. Automations

Switches and remotes provide **device triggers**: **Settings → Automations → Create → Add trigger → Device**, pick the switch, then the trigger (e.g. "Top left pressed", "Double press"). For other products use the usual entity triggers (motion detected, opened, card inserted…).

YAML example — wall switch, top left = on, bottom left = off:

```yaml
triggers:
  - trigger: state
    entity_id: event.living_room_switch_keys
actions:
  - choose:
      - conditions: "{{ trigger.to_state.attributes.event_type == 'left_up' }}"
        sequence:
          - action: light.turn_on
            target: { entity_id: light.living_room }
      - conditions: "{{ trigger.to_state.attributes.event_type == 'left_down' }}"
        sequence:
          - action: light.turn_off
            target: { entity_id: light.living_room }
```

`event_type` values: `left_up`, `left_down`, `right_up`, `right_down`, combinations such as `left_up_right_up`, `release`; 2-button faceplate: `up`, `down`; Soft Button: `single`, `double`, `long`, `long_release`; floor switch: `press`, `release`. Duplicate telegrams sent by modules in repeater mode are filtered automatically.

## 8. Help and troubleshooting

- **NodOn help button** (Diagnostic card): press it, then open **Notifications** for the user guide, NodOn support, contact form and the product's EnOcean ID.
- **Download diagnostics**: **⋮** on the EnOcean stick row (whole integration) or on a device page (one product). The file contains versions, products, settings and the last 100 radio telegrams — attach it to bug reports.
- **Repairs**: "EnOcean stick unreachable" or "stick used by the native EnOcean integration" alerts appear in **Settings → System → Repairs** and disappear once the stick answers.
- **Debug logs** (`configuration.yaml`):

```yaml
logger:
  logs:
    custom_components.nodon_enocean: debug
```

Report problems with the [bug report form](https://github.com/eHomeLabs/NodOcean-for-HA/issues/new?template=bug.yml).

## 9. FAQ

**Do I need MQTT, an add-on or an EnOcean hub?** No, just a USB300 (or ESP3-compatible) stick.

**Can I keep the native EnOcean integration?** Not on the same stick.

**My products are paired with another hub.** Sensors and switches can be paired to several receivers. For relay modules and plugs, pair from Home Assistant; if it fails, factory-reset the product first.

**Do direct links still work (switch → module without Home Assistant)?** Yes, and Home Assistant shows the module's new state.

**Are NodOn Zigbee products supported?** No, use ZHA or Zigbee2MQTT.

**Radio range?** About 30 m indoors depending on walls; enable the repeater of a module placed in between.
