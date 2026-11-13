"""Names of the sensors read from `extended`, in the ten languages of the app.

Imported by make_translations.py. KEYS is the order of every list below.
"""

from __future__ import annotations

KEYS = [
    "engine_load", "intake_temperature", "outside_temperature", "oil_temperature",
    "accelerator_pedal", "intake_pressure", "mass_air_flow", "fuel_rate",
    "timing_advance", "short_fuel_trim", "long_fuel_trim", "barometric_pressure",
    "engine_run_time", "fuel_rail_pressure", "distance_with_mil",
    "distance_since_codes_cleared", "torque", "power", "catalyst_temperature",
    "exhaust_temperature", "dpf_temperature", "dpf_pressure_difference",
    "dpf_soot_calculated", "dpf_soot_measured", "dpf_load",
    "distance_since_dpf_regeneration", "adblue_level", "gearbox_temperature",
    "hv_battery_health", "hv_battery_temperature",
]
BINARY_KEYS = ["dpf_regenerating"]

_NAMES = {
    "en": [
        "Engine load", "Intake air temperature", "Outside temperature", "Oil temperature",
        "Accelerator pedal", "Intake manifold pressure", "Mass air flow", "Fuel rate",
        "Timing advance", "Short-term fuel trim", "Long-term fuel trim", "Barometric pressure",
        "Engine run time", "Fuel rail pressure", "Distance with engine light on",
        "Distance since codes cleared", "Torque", "Power", "Catalyst temperature",
        "Exhaust gas temperature", "DPF temperature", "DPF differential pressure",
        "DPF soot (calculated)", "DPF soot (measured)", "DPF load",
        "Distance since DPF regeneration", "AdBlue level", "Gearbox temperature",
        "HV battery health", "HV battery temperature",
        "DPF regenerating",
    ],
    "it": [
        "Carico motore", "Temperatura aria aspirata", "Temperatura esterna", "Temperatura olio",
        "Pedale acceleratore", "Pressione collettore", "Flusso aria", "Consumo orario",
        "Anticipo accensione", "Correzione carburante breve", "Correzione carburante lunga", "Pressione atmosferica",
        "Tempo motore acceso", "Pressione rail", "Distanza con spia motore accesa",
        "Distanza dalla cancellazione codici", "Coppia", "Potenza", "Temperatura catalizzatore",
        "Temperatura gas di scarico", "Temperatura DPF", "Pressione differenziale DPF",
        "Particolato DPF (calcolato)", "Particolato DPF (misurato)", "Carico DPF",
        "Distanza dalla rigenerazione DPF", "Livello AdBlue", "Temperatura cambio",
        "Salute batteria HV", "Temperatura batteria HV",
        "Rigenerazione DPF in corso",
    ],
    "de": [
        "Motorlast", "Ansauglufttemperatur", "Außentemperatur", "Öltemperatur",
        "Gaspedal", "Saugrohrdruck", "Luftmassenstrom", "Kraftstoffverbrauch pro Stunde",
        "Zündzeitpunkt", "Kurzzeit-Gemischkorrektur", "Langzeit-Gemischkorrektur", "Luftdruck",
        "Motorlaufzeit", "Raildruck", "Strecke mit Motorkontrollleuchte",
        "Strecke seit Fehlerlöschung", "Drehmoment", "Leistung", "Katalysatortemperatur",
        "Abgastemperatur", "DPF-Temperatur", "DPF-Differenzdruck",
        "DPF-Ruß (berechnet)", "DPF-Ruß (gemessen)", "DPF-Beladung",
        "Strecke seit DPF-Regeneration", "AdBlue-Füllstand", "Getriebetemperatur",
        "HV-Batteriezustand", "HV-Batterietemperatur",
        "DPF-Regeneration läuft",
    ],
    "fr": [
        "Charge moteur", "Température de l'air d'admission", "Température extérieure", "Température d'huile",
        "Pédale d'accélérateur", "Pression du collecteur", "Débit d'air", "Débit de carburant",
        "Avance à l'allumage", "Correction carburant court terme", "Correction carburant long terme", "Pression atmosphérique",
        "Temps de fonctionnement du moteur", "Pression de rampe", "Distance avec voyant moteur allumé",
        "Distance depuis l'effacement des codes", "Couple", "Puissance", "Température du catalyseur",
        "Température des gaz d'échappement", "Température du FAP", "Pression différentielle du FAP",
        "Suie du FAP (calculée)", "Suie du FAP (mesurée)", "Charge du FAP",
        "Distance depuis la régénération du FAP", "Niveau d'AdBlue", "Température de la boîte de vitesses",
        "Santé de la batterie HT", "Température de la batterie HT",
        "Régénération du FAP en cours",
    ],
    "es": [
        "Carga del motor", "Temperatura del aire de admisión", "Temperatura exterior", "Temperatura del aceite",
        "Pedal del acelerador", "Presión del colector", "Flujo de aire", "Consumo por hora",
        "Avance del encendido", "Ajuste de combustible a corto plazo", "Ajuste de combustible a largo plazo", "Presión barométrica",
        "Tiempo de motor en marcha", "Presión del rail", "Distancia con testigo de motor encendido",
        "Distancia desde el borrado de códigos", "Par", "Potencia", "Temperatura del catalizador",
        "Temperatura de gases de escape", "Temperatura del DPF", "Presión diferencial del DPF",
        "Hollín del DPF (calculado)", "Hollín del DPF (medido)", "Carga del DPF",
        "Distancia desde la regeneración del DPF", "Nivel de AdBlue", "Temperatura de la caja de cambios",
        "Salud de la batería de alta tensión", "Temperatura de la batería de alta tensión",
        "Regeneración del DPF en curso",
    ],
    "pt": [
        "Carga do motor", "Temperatura do ar de admissão", "Temperatura exterior", "Temperatura do óleo",
        "Pedal do acelerador", "Pressão do coletor", "Fluxo de ar", "Consumo por hora",
        "Avanço da ignição", "Correção de combustível de curto prazo", "Correção de combustível de longo prazo", "Pressão atmosférica",
        "Tempo de motor ligado", "Pressão do rail", "Distância com luz do motor acesa",
        "Distância desde a limpeza dos códigos", "Binário", "Potência", "Temperatura do catalisador",
        "Temperatura dos gases de escape", "Temperatura do DPF", "Pressão diferencial do DPF",
        "Fuligem do DPF (calculada)", "Fuligem do DPF (medida)", "Carga do DPF",
        "Distância desde a regeneração do DPF", "Nível de AdBlue", "Temperatura da caixa de velocidades",
        "Saúde da bateria de alta tensão", "Temperatura da bateria de alta tensão",
        "Regeneração do DPF em curso",
    ],
    "cs": [
        "Zatížení motoru", "Teplota nasávaného vzduchu", "Venkovní teplota", "Teplota oleje",
        "Pedál plynu", "Tlak v sacím potrubí", "Hmotnostní průtok vzduchu", "Spotřeba za hodinu",
        "Předstih zapalování", "Krátkodobá korekce paliva", "Dlouhodobá korekce paliva", "Barometrický tlak",
        "Doba chodu motoru", "Tlak v rozdělovači paliva", "Vzdálenost s kontrolkou motoru",
        "Vzdálenost od vymazání kódů", "Točivý moment", "Výkon", "Teplota katalyzátoru",
        "Teplota výfukových plynů", "Teplota DPF", "Diferenční tlak DPF",
        "Saze v DPF (vypočtené)", "Saze v DPF (změřené)", "Zaplnění DPF",
        "Vzdálenost od regenerace DPF", "Hladina AdBlue", "Teplota převodovky",
        "Stav VN baterie", "Teplota VN baterie",
        "Probíhá regenerace DPF",
    ],
    "hu": [
        "Motorterhelés", "Beszívott levegő hőmérséklete", "Külső hőmérséklet", "Olajhőmérséklet",
        "Gázpedál", "Szívócsőnyomás", "Légtömegmérő", "Óránkénti fogyasztás",
        "Gyújtási szög", "Rövid távú üzemanyag-korrekció", "Hosszú távú üzemanyag-korrekció", "Légnyomás",
        "Motor üzemideje", "Rail nyomás", "Megtett táv motorhiba-lámpával",
        "Megtett táv a kódok törlése óta", "Nyomaték", "Teljesítmény", "Katalizátor hőmérséklete",
        "Kipufogógáz hőmérséklete", "DPF hőmérséklet", "DPF nyomáskülönbség",
        "DPF korom (számított)", "DPF korom (mért)", "DPF telítettség",
        "Megtett táv a DPF regenerálás óta", "AdBlue szint", "Váltó hőmérséklete",
        "Nagyfeszültségű akkumulátor állapota", "Nagyfeszültségű akkumulátor hőmérséklete",
        "DPF regenerálás folyamatban",
    ],
    "pl": [
        "Obciążenie silnika", "Temperatura powietrza dolotowego", "Temperatura zewnętrzna", "Temperatura oleju",
        "Pedał przyspieszenia", "Ciśnienie w kolektorze", "Przepływ powietrza", "Zużycie paliwa na godzinę",
        "Kąt wyprzedzenia zapłonu", "Krótkoterminowa korekta paliwa", "Długoterminowa korekta paliwa", "Ciśnienie atmosferyczne",
        "Czas pracy silnika", "Ciśnienie na listwie paliwowej", "Dystans z kontrolką silnika",
        "Dystans od skasowania kodów", "Moment obrotowy", "Moc", "Temperatura katalizatora",
        "Temperatura spalin", "Temperatura DPF", "Różnica ciśnień DPF",
        "Sadza w DPF (obliczona)", "Sadza w DPF (zmierzona)", "Zapełnienie DPF",
        "Dystans od regeneracji DPF", "Poziom AdBlue", "Temperatura skrzyni biegów",
        "Kondycja baterii WN", "Temperatura baterii WN",
        "Trwa regeneracja DPF",
    ],
    "ro": [
        "Sarcină motor", "Temperatura aerului admis", "Temperatura exterioară", "Temperatura uleiului",
        "Pedala de accelerație", "Presiunea din galerie", "Debit de aer", "Consum pe oră",
        "Avans la aprindere", "Corecție combustibil pe termen scurt", "Corecție combustibil pe termen lung", "Presiune atmosferică",
        "Timp de funcționare a motorului", "Presiunea din rampa de combustibil", "Distanță cu martorul motorului aprins",
        "Distanță de la ștergerea codurilor", "Cuplu", "Putere", "Temperatura catalizatorului",
        "Temperatura gazelor de evacuare", "Temperatura DPF", "Presiune diferențială DPF",
        "Funingine DPF (calculată)", "Funingine DPF (măsurată)", "Încărcare DPF",
        "Distanță de la regenerarea DPF", "Nivel AdBlue", "Temperatura cutiei de viteze",
        "Sănătatea bateriei de înaltă tensiune", "Temperatura bateriei de înaltă tensiune",
        "Regenerare DPF în curs",
    ],
}


def names(lang: str) -> tuple[dict[str, str], dict[str, str]]:
    """The sensor names and the binary sensor names of one language."""
    found = dict(zip(KEYS + BINARY_KEYS, _NAMES[lang], strict=True))
    return {k: found[k] for k in KEYS}, {k: found[k] for k in BINARY_KEYS}
