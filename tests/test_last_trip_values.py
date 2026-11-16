"""The numbers of the last trip as their own sensors, and obd_at in the events.

Duration, average and maximum speed and average consumption were only
attributes of Last trip: no unit, no history. The trip events passed sent_at
but not obd_at, which the app sends in every message.
"""

from __future__ import annotations

from typing import Any

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from custom_components.drivepulse.const import EVENT_TRIP_END, EVENT_TRIP_START

from .conftest import find, message


def trip_end(**trip_fields: Any) -> dict[str, Any]:
    body = message("trip_end", odometer_km=20364.8)
    body["trip"] = {
        "id": 9,
        "start": "2026-10-12T07:00:00Z",
        "end": "2026-10-12T07:40:00Z",
        "distance_km": 31.5,
        "duration_min": 40.0,
        "avg_speed_kmh": 47.3,
        "max_speed_kmh": 110.0,
        "odometer_km": None,
        **trip_fields,
    }
    return body


def value(hass: HomeAssistant, entry, key: str) -> str | None:
    entity_id = find(hass, entry, "sensor", key)
    return hass.states.get(entity_id).state if entity_id else None


async def test_a_petrol_trip_fills_its_four_sensors(
    hass: HomeAssistant, entry, send
) -> None:
    assert await send(trip_end(avg_consumption_l_100km=6.1)) == 200

    assert value(hass, entry, "last_trip_duration") == "40.0"
    assert value(hass, entry, "last_trip_average_speed") == "47.3"
    assert value(hass, entry, "last_trip_max_speed") == "110.0"
    assert value(hass, entry, "last_trip_consumption") == "6.1"
    # the attributes of Last trip stay as they were
    last = hass.states.get(find(hass, entry, "sensor", "last_trip_distance"))
    assert last.state == "31.5"
    assert last.attributes["duration_min"] == 40.0
    # a petrol car never gets an electric consumption
    assert find(hass, entry, "sensor", "last_trip_electric_consumption") is None


async def test_an_electric_trip_gets_kwh_and_no_litres(
    hass: HomeAssistant, entry, send
) -> None:
    await send(trip_end(avg_consumption_kwh_100km=15.8))

    assert value(hass, entry, "last_trip_electric_consumption") == "15.8"
    assert find(hass, entry, "sensor", "last_trip_consumption") is None
    unit = hass.states.get(
        find(hass, entry, "sensor", "last_trip_electric_consumption")
    ).attributes["unit_of_measurement"]
    assert unit == "kWh/100km"


async def test_without_a_trip_they_are_unavailable_not_zero(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message("live"))

    assert value(hass, entry, "last_trip_duration") == STATE_UNAVAILABLE
    assert value(hass, entry, "last_trip_max_speed") == STATE_UNAVAILABLE
    assert find(hass, entry, "sensor", "last_trip_consumption") is None


async def test_a_trip_without_consumption_blanks_the_sensor(
    hass: HomeAssistant, entry, send
) -> None:
    await send(trip_end(avg_consumption_l_100km=6.1))
    later = trip_end(avg_consumption_l_100km=None)
    later["trip"]["end"] = "2026-10-12T09:00:00Z"
    await send(later)

    assert value(hass, entry, "last_trip_consumption") == STATE_UNAVAILABLE
    assert value(hass, entry, "last_trip_duration") == "40.0"


async def test_they_survive_a_reload(hass: HomeAssistant, entry, send) -> None:
    await send(trip_end(avg_consumption_l_100km=6.1))

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert value(hass, entry, "last_trip_consumption") == "6.1"
    assert value(hass, entry, "last_trip_average_speed") == "47.3"


async def test_trip_events_carry_obd_at(hass: HomeAssistant, entry, send) -> None:
    events = []
    hass.bus.async_listen(EVENT_TRIP_START, events.append)
    hass.bus.async_listen(EVENT_TRIP_END, events.append)

    await send(message("trip_start", obd_at="2026-10-12T06:59:58.000Z"))
    # engine already off at the end: the app heard the car earlier, or never
    await send(trip_end() | {"obd_at": None})

    assert [e.data["obd_at"] for e in events] == ["2026-10-12T06:59:58.000Z", None]
    assert all("sent_at" in e.data for e in events)
