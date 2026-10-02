"""Catalogue des produits EnOcean NodOn pris en charge.

Sources : Quick User Guides de l'Integration Kit NodOn, notices utilisateur,
fiches techniques (support.nodon.fr) — voir docs/PRODUITS.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Types d'appairage
TEACH_UTE_BIDIR = "ute_bidir"  # l'appareil envoie une requête UTE, HA répond
TEACH_UTE_UNI = "ute_uni"  # requête UTE sans réponse (Soft Button)
TEACH_1BS = "1bs"  # télégramme 1BS avec bit LRN
TEACH_4BS = "4bs"  # télégramme 4BS avec bit LRN
TEACH_RPS = "rps"  # premier appui de touche reçu

_IMAGES = "https://raw.githubusercontent.com/eHomeLabs/nodon-enocean-ha/main/docs/images/products/"


@dataclass(frozen=True)
class Product:
    model: str
    name_fr: str
    name_en: str
    eep: str
    teach_in: str
    pairing_fr: str
    pairing_en: str
    channels: int = 1
    metering: bool = False
    url: str | None = None
    after_fr: str = ""
    after_en: str = ""
    variants: tuple[str, ...] = field(default_factory=tuple)

    @property
    def image(self) -> str:
        return f"{_IMAGES}{self.model}.png"

    @property
    def references(self) -> str:
        """Références commerciales complètes (ex. « ASP-2-1-00 / ASP-2-1-10 »)."""
        return " / ".join(self.variants) if self.variants else self.model

    @property
    def is_actuator(self) -> bool:
        return self.teach_in == TEACH_UTE_BIDIR

    @property
    def rorg_func_type(self) -> tuple[int, int, int]:
        rorg, func, type_ = (int(x, 16) for x in self.eep.split("-"))
        return rorg, func, type_

    def name(self, lang: str) -> str:
        return self.name_fr if lang.startswith("fr") else self.name_en

    def pairing(self, lang: str) -> str:
        return self.pairing_fr if lang.startswith("fr") else self.pairing_en

    def after(self, lang: str) -> str:
        return self.after_fr if lang.startswith("fr") else self.after_en


_ACT_FR = (
    "Le module envoie alors sa demande d'appairage : Home Assistant répond "
    "automatiquement, la LED clignote 2 fois en vert."
)
_ACT_EN = (
    "The module then sends its pairing request: Home Assistant answers "
    "automatically and the LED blinks green twice."
)

PRODUCTS: dict[str, Product] = {
    p.model: p
    for p in (
        Product(
            model="SIN-2-1-01",
            name_fr="Module Multifonction EnOcean",
            name_en="EnOcean Multifunction Relay Switch",
            eep="D2-01-0F",
            teach_in=TEACH_UTE_BIDIR,
            pairing_fr=(
                "Le module doit être sous tension. Appuyez **3 fois rapidement** sur "
                "le bouton du module : la LED scintille en rouge (30 s). " + _ACT_FR
            ),
            pairing_en=(
                "The module must be powered. Press the module button **3 times "
                "quickly**: the LED flickers red (30 s). " + _ACT_EN
            ),
            url="https://nodon.fr/products/module-multifonction-enocean",
        ),
        Product(
            model="SIN-2-2-01",
            name_fr="Module Éclairage ON/OFF EnOcean (2 canaux)",
            name_en="EnOcean ON/OFF Lighting Relay Switch (2 channels)",
            eep="D2-01-12",
            teach_in=TEACH_UTE_BIDIR,
            channels=2,
            pairing_fr=(
                "Le module doit être sous tension. Appuyez **3 fois rapidement** sur "
                "le bouton du module : la LED scintille en rouge (30 s). Les 2 canaux "
                "sont appairés en une seule fois. " + _ACT_FR
            ),
            pairing_en=(
                "The module must be powered. Press the module button **3 times "
                "quickly**: the LED flickers red (30 s). Both channels are paired at "
                "once. " + _ACT_EN
            ),
            url="https://nodon.fr/products/module-eclairage-on-off-enocean",
        ),
        Product(
            model="SIN-2-FP-01",
            name_fr="Module Chauffage Fil Pilote EnOcean",
            name_en="EnOcean Pilot Wire Heating Module",
            eep="D2-01-0C",
            teach_in=TEACH_UTE_BIDIR,
            metering=True,
            pairing_fr=(
                "Le module doit être sous tension. Appuyez **3 fois rapidement** "
                "(en moins de 2 s) sur le bouton du module : la LED scintille en "
                "rouge (30 s). " + _ACT_FR
            ),
            pairing_en=(
                "The module must be powered. Press the module button **3 times "
                "quickly** (within 2 s): the LED flickers red (30 s). " + _ACT_EN
            ),
            url="https://nodon.fr/products/module-chauffage-fil-pilote-enocean",
        ),
        Product(
            model="SIN-2-RS-01",
            name_fr="Module Volet Roulant EnOcean",
            name_en="EnOcean Roller Shutter Relay Switch",
            eep="D2-05-00",
            teach_in=TEACH_UTE_BIDIR,
            pairing_fr=(
                "Le module doit être sous tension. Appuyez **3 fois rapidement** sur "
                "le bouton du module : la LED scintille en rouge (30 s). " + _ACT_FR
            ),
            pairing_en=(
                "The module must be powered. Press the module button **3 times "
                "quickly**: the LED flickers red (30 s). " + _ACT_EN
            ),
            after_fr=(
                "Pensez à calibrer le volet si ce n'est pas déjà fait : 5 appuis "
                "brefs sur le bouton du module (cycle montée / descente / montée)."
            ),
            after_en=(
                "Remember to calibrate the shutter if not done yet: 5 short presses "
                "on the module button (up / down / up cycle)."
            ),
            url="https://nodon.fr/products/module-volet-roulant-enocean",
        ),
        Product(
            model="ASP-2",
            name_fr="Prise intelligente EnOcean",
            name_en="EnOcean Smart Plug",
            eep="D2-01-0A",
            teach_in=TEACH_UTE_BIDIR,
            variants=("ASP-2-1-00", "ASP-2-1-10"),
            pairing_fr=(
                "Branchez la prise. Maintenez le bouton **2 secondes** jusqu'à ce que "
                "la LED passe au rouge, puis relâchez : la prise envoie une demande "
                "d'appairage toutes les 3 s pendant 30 s. Home Assistant répond "
                "automatiquement, la LED clignote en vert."
            ),
            pairing_en=(
                "Plug in the Smart Plug. Hold the button for **2 seconds** until the "
                "LED turns red, then release: the plug sends a pairing request every "
                "3 s for 30 s. Home Assistant answers automatically and the LED "
                "blinks green."
            ),
        ),
        Product(
            model="MSP-2",
            name_fr="Micro Smart Plug EnOcean + Mesure",
            name_en="EnOcean Micro Smart Plug + Metering",
            eep="D2-01-0E",
            teach_in=TEACH_UTE_BIDIR,
            metering=True,
            variants=("MSP-2-1-01", "MSP-2-1-11"),
            pairing_fr=(
                "Branchez la prise. Maintenez le bouton **2 secondes** jusqu'à ce que "
                "la LED passe au rouge, puis relâchez : la prise envoie une demande "
                "d'appairage toutes les 3 s pendant 30 s. Home Assistant répond "
                "automatiquement, la LED clignote en vert."
            ),
            pairing_en=(
                "Plug in the Micro Smart Plug. Hold the button for **2 seconds** until "
                "the LED turns red, then release: the plug sends a pairing request "
                "every 3 s for 30 s. Home Assistant answers automatically and the LED "
                "blinks green."
            ),
        ),
        Product(
            model="CWS-2-1",
            name_fr="Interrupteur mural EnOcean (sans pile)",
            name_en="EnOcean Wall Switch (battery-free)",
            eep="F6-02-01",
            teach_in=TEACH_RPS,
            variants=("CWS-2-1-01",),
            pairing_fr=(
                "Appuyez franchement sur **une touche** de l'interrupteur. "
                "Toutes les touches seront ensuite disponibles dans Home Assistant."
            ),
            pairing_en=(
                "Firmly press **any key** of the switch. All keys will then be "
                "available in Home Assistant."
            ),
            url="https://nodon.fr/products/enocean-wall-switch",
        ),
        Product(
            model="TSB-2",
            name_fr="Soft Button EnOcean",
            name_en="EnOcean Soft Button",
            eep="D2-03-0A",
            teach_in=TEACH_UTE_UNI,
            variants=("TSB-2-2-02",),
            pairing_fr=(
                "Appuyez **5 fois brièvement** de suite sur le Soft Button "
                "(moins d'une demi-seconde entre chaque appui)."
            ),
            pairing_en=(
                "Press the Soft Button **5 times briefly** in a row "
                "(less than half a second between presses)."
            ),
            url="https://nodon.fr/products/soft-button-enocean",
        ),
        Product(
            model="SDO-2",
            name_fr="Détecteur d'ouverture portes et fenêtres EnOcean",
            name_en="EnOcean Door and Window Sensor",
            eep="D5-00-01",
            teach_in=TEACH_1BS,
            variants=("SDO-2-1-05",),
            pairing_fr=(
                "Faites **un appui simple** sur le bouton d'appairage situé à "
                "l'arrière du capteur. Si le capteur est neuf, exposez-le quelques "
                "minutes à la lumière pour charger sa cellule solaire."
            ),
            pairing_en=(
                "Press **once** the pairing button at the back of the sensor. If the "
                "sensor is new, expose it to light for a few minutes to charge its "
                "solar cell."
            ),
            url="https://nodon.fr/products/capteur-ouverture-portes-et-fenetres-enocean",
        ),
        Product(
            model="SWO-2",
            name_fr="Capteur d'ouverture invisible sans pile EnOcean",
            name_en="EnOcean Battery-free Invisible Opening Sensor",
            eep="D5-00-01",
            teach_in=TEACH_1BS,
            variants=("SWO-2-1-00",),
            pairing_fr=(
                "**Maintenez le bouton LRN** du capteur enfoncé **et actionnez le "
                "ressort** (enfoncez-le ou relâchez-le). Le bouton LRN seul n'émet rien."
            ),
            pairing_en=(
                "**Hold the LRN button** of the sensor **and actuate the spring** "
                "(press or release it). The LRN button alone sends nothing."
            ),
            url="https://nodon.fr/products/capteur-ouverture-invisible-sans-pile-enocean",
        ),
        Product(
            model="STP-2",
            name_fr="Capteur de température EnOcean",
            name_en="EnOcean Temperature Sensor",
            eep="A5-02-05",
            teach_in=TEACH_4BS,
            variants=("STP-2-1-05",),
            pairing_fr=(
                "Faites **un appui** sur le bouton d'appairage situé à l'arrière du "
                "capteur. Si le capteur est neuf, exposez-le quelques minutes à la "
                "lumière pour charger sa cellule solaire."
            ),
            pairing_en=(
                "Press the pairing button at the back of the sensor **once**. If the "
                "sensor is new, expose it to light for a few minutes to charge its "
                "solar cell."
            ),
            url="https://nodon.fr/products/capteur-de-temperature-enocean",
        ),
        Product(
            model="STPH-2",
            name_fr="Capteur de température et d'humidité EnOcean",
            name_en="EnOcean Temperature and Humidity Sensor",
            eep="A5-04-01",
            teach_in=TEACH_4BS,
            variants=("STPH-2-1-05",),
            pairing_fr=(
                "Faites **un appui** sur le bouton d'appairage situé à l'arrière du "
                "capteur. Si le capteur est neuf, exposez-le quelques minutes à la "
                "lumière pour charger sa cellule solaire."
            ),
            pairing_en=(
                "Press the pairing button at the back of the sensor **once**. If the "
                "sensor is new, expose it to light for a few minutes to charge its "
                "solar cell."
            ),
        ),
    )
}
