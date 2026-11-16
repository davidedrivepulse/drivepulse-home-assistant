"""Texts of the options menu and of the custom PID sources, in the ten languages.

Imported by make_translations.py. The field labels of the sources form are
the sensor names, so they are not repeated here.
"""

from __future__ import annotations

TEXTS = {
    "en": {
        "network": "Network",
        "sources": "Values from custom PIDs",
        "vehicle": "Vehicle",
        "sources_desc": "{vehicle}: if the car gives a wrong number for one of these (for example a battery charge that is always 0), pick a custom PID that reads it right, and the sensor and the trip events use that instead. Leave a field empty for the app's own value. When Home Assistant knows both units, the value is converted.",
        "wrong_unit": "The unit of this custom PID does not fit this sensor.",
        "no_custom_pids": "No vehicle has sent a custom PID yet. Set one up in the app, then come back after the next message from the car.",
    },
    "it": {
        "network": "Rete",
        "sources": "Valori dai PID personalizzati",
        "vehicle": "Veicolo",
        "sources_desc": "{vehicle}: se l'auto dà un numero sbagliato per uno di questi (per esempio una carica della batteria sempre a 0), scegli un PID personalizzato che lo legge bene: il sensore e gli eventi del viaggio useranno quello. Lascia vuoto un campo per il valore dell'app. Se Home Assistant conosce entrambe le unità, il valore viene convertito.",
        "wrong_unit": "L'unità di questo PID personalizzato non è adatta a questo sensore.",
        "no_custom_pids": "Nessun veicolo ha ancora inviato un PID personalizzato. Configuralo nell'app, poi torna qui dopo il prossimo messaggio dell'auto.",
    },
    "de": {
        "network": "Netzwerk",
        "sources": "Werte aus eigenen PIDs",
        "vehicle": "Fahrzeug",
        "sources_desc": "{vehicle}: Liefert das Auto für einen dieser Werte eine falsche Zahl (zum Beispiel eine Batterieladung, die immer 0 ist), wählen Sie eine eigene PID, die ihn richtig liest: Sensor und Fahrtereignisse verwenden dann diese. Lassen Sie ein Feld leer für den Wert der App. Kennt Home Assistant beide Einheiten, wird der Wert umgerechnet.",
        "wrong_unit": "Die Einheit dieser eigenen PID passt nicht zu diesem Sensor.",
        "no_custom_pids": "Noch kein Fahrzeug hat eine eigene PID gesendet. Richten Sie eine in der App ein und kommen Sie nach der nächsten Nachricht des Autos zurück.",
    },
    "fr": {
        "network": "Réseau",
        "sources": "Valeurs des PID personnalisés",
        "vehicle": "Véhicule",
        "sources_desc": "{vehicle} : si la voiture donne un mauvais chiffre pour l'une de ces valeurs (par exemple une charge de batterie toujours à 0), choisissez un PID personnalisé qui la lit correctement : le capteur et les événements de trajet l'utiliseront. Laissez un champ vide pour la valeur de l'application. Si Home Assistant connaît les deux unités, la valeur est convertie.",
        "wrong_unit": "L'unité de ce PID personnalisé ne convient pas à ce capteur.",
        "no_custom_pids": "Aucun véhicule n'a encore envoyé de PID personnalisé. Configurez-en un dans l'application, puis revenez après le prochain message de la voiture.",
    },
    "es": {
        "network": "Red",
        "sources": "Valores de PID personalizados",
        "vehicle": "Vehículo",
        "sources_desc": "{vehicle}: si el coche da un número erróneo para alguno de estos valores (por ejemplo una carga de batería siempre en 0), elige un PID personalizado que lo lea bien: el sensor y los eventos del viaje usarán ese. Deja un campo vacío para el valor de la app. Si Home Assistant conoce ambas unidades, el valor se convierte.",
        "wrong_unit": "La unidad de este PID personalizado no corresponde a este sensor.",
        "no_custom_pids": "Ningún vehículo ha enviado aún un PID personalizado. Configura uno en la app y vuelve después del próximo mensaje del coche.",
    },
    "pt": {
        "network": "Rede",
        "sources": "Valores de PIDs personalizados",
        "vehicle": "Veículo",
        "sources_desc": "{vehicle}: se o carro dá um número errado para algum destes valores (por exemplo uma carga da bateria sempre a 0), escolha um PID personalizado que o leia bem: o sensor e os eventos da viagem usarão esse. Deixe um campo vazio para o valor da app. Se o Home Assistant conhecer as duas unidades, o valor é convertido.",
        "wrong_unit": "A unidade deste PID personalizado não corresponde a este sensor.",
        "no_custom_pids": "Nenhum veículo enviou ainda um PID personalizado. Configure um na app e volte depois da próxima mensagem do carro.",
    },
    "cs": {
        "network": "Síť",
        "sources": "Hodnoty z vlastních PID",
        "vehicle": "Vozidlo",
        "sources_desc": "{vehicle}: pokud auto u některé z těchto hodnot posílá špatné číslo (například nabití baterie stále 0), vyberte vlastní PID, který ji čte správně: senzor i události jízdy pak použijí ten. Pole nechte prázdné pro hodnotu z aplikace. Pokud Home Assistant zná obě jednotky, hodnota se převede.",
        "wrong_unit": "Jednotka tohoto vlastního PID neodpovídá tomuto senzoru.",
        "no_custom_pids": "Žádné vozidlo zatím neposlalo vlastní PID. Nastavte ho v aplikaci a vraťte se po další zprávě z auta.",
    },
    "hu": {
        "network": "Hálózat",
        "sources": "Értékek egyéni PID-ekből",
        "vehicle": "Jármű",
        "sources_desc": "{vehicle}: ha az autó ezek közül valamelyikre rossz számot ad (például az akkumulátor töltöttsége mindig 0), válasszon egy egyéni PID-et, amely helyesen olvassa: az érzékelő és az út eseményei azt használják. Hagyja üresen a mezőt az alkalmazás saját értékéhez. Ha a Home Assistant mindkét mértékegységet ismeri, az értéket átváltja.",
        "wrong_unit": "Ennek az egyéni PID-nek a mértékegysége nem illik ehhez az érzékelőhöz.",
        "no_custom_pids": "Még egyetlen jármű sem küldött egyéni PID-et. Állítson be egyet az alkalmazásban, és térjen vissza az autó következő üzenete után.",
    },
    "pl": {
        "network": "Sieć",
        "sources": "Wartości z własnych PID",
        "vehicle": "Pojazd",
        "sources_desc": "{vehicle}: jeśli auto podaje błędną liczbę dla którejś z tych wartości (na przykład naładowanie baterii zawsze 0), wybierz własny PID, który odczytuje ją poprawnie: czujnik i zdarzenia podróży użyją go zamiast tego. Zostaw pole puste, aby zachować wartość z aplikacji. Jeśli Home Assistant zna obie jednostki, wartość zostanie przeliczona.",
        "wrong_unit": "Jednostka tego własnego PID nie pasuje do tego czujnika.",
        "no_custom_pids": "Żaden pojazd nie wysłał jeszcze własnego PID. Skonfiguruj go w aplikacji i wróć po następnej wiadomości z auta.",
    },
    "ro": {
        "network": "Rețea",
        "sources": "Valori din PID-uri personalizate",
        "vehicle": "Vehicul",
        "sources_desc": "{vehicle}: dacă mașina dă un număr greșit pentru una dintre aceste valori (de exemplu o încărcare a bateriei mereu 0), alege un PID personalizat care o citește corect: senzorul și evenimentele călătoriei îl vor folosi pe acesta. Lasă un câmp gol pentru valoarea aplicației. Dacă Home Assistant cunoaște ambele unități, valoarea este convertită.",
        "wrong_unit": "Unitatea acestui PID personalizat nu se potrivește cu acest senzor.",
        "no_custom_pids": "Niciun vehicul nu a trimis încă un PID personalizat. Configurează unul în aplicație, apoi revino după următorul mesaj al mașinii.",
    },
}

SOURCE_KEYS = [
    "battery_level", "fuel_level", "range", "odometer", "battery_voltage",
    "coolant_temperature", "fuel_volume", "speed", "engine_speed",
]


def options(lang: str, opt_desc: str, local_only: str, local_only_desc: str,
            sensor_names: dict[str, str]) -> dict:
    """The `options` block of one translation file."""
    t = TEXTS[lang]
    return {
        "step": {
            "init": {
                "description": opt_desc,
                "menu_options": {"network": t["network"], "sources": t["sources"]},
            },
            "network": {
                "title": t["network"],
                "description": opt_desc,
                "data": {"local_only": local_only},
                "data_description": {"local_only": local_only_desc},
            },
            "sources": {
                "title": t["sources"],
                "data": {"vehicle": t["vehicle"]},
            },
            "vehicle_sources": {
                "title": t["sources"],
                "description": t["sources_desc"],
                "data": {k: sensor_names[k] for k in SOURCE_KEYS},
            },
        },
        "error": {"wrong_unit": t["wrong_unit"]},
        "abort": {"no_custom_pids": t["no_custom_pids"]},
    }
