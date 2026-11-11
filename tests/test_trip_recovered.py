"""trip_recovered: a real trip left open when the phone stopped the app.

The app closes it with its real end time when it opens again, maybe hours
later. Until now it only went to the app's database: no trip_end, and Trip in
progress stayed on in Home Assistant.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.drivepulse.const import (
    EVENT_TRIP_END,
    EVENT_TRIP_RESENT,
    EVENT_TRIP_START,
)

from .conftest import find, message

NULLS = {
    key: None
    for key in (
        "rpm",
        "speed_kmh",
        "coolant_temp_c",
        "battery_voltage",
        "fuel_level_pct",
        "throttle_pct",
        "consumption_l_100km",
        "trip_km",
        "dtc_count",
        "fuel_level_l",
        "range_km",
        "hv_soc_pct",
        "odometer_km",
        "dtc",
        "obd_at",
    )
}


def trip(end: str, distance_km: float = 31.5, **fields: Any) -> dict[str, Any]:
    return {
        "id": 9,
        "start": "2026-10-12T07:00:00Z",
        "end": end,
        "distance_km": distance_km,
        "duration_min": 40.0,
        "avg_speed_kmh": 47.3,
        "max_speed_kmh": 110.0,
        "avg_consumption_l_100km": 6.1,
        "odometer_km": None,
        **fields,
    }


def recovered(the_trip: Any = None, **fields: Any) -> dict[str, Any]:
    """Shaped like the app's: every reading null, the trip apart."""
    body = message("trip_recovered", obd_connected=False, **NULLS, **fields)
    if the_trip is not None:
        body["trip"] = the_trip
    return body


def state(hass: HomeAssistant, entry, domain: str, key: str, vehicle: str = "my_car"):
    entity_id = find(hass, entry, domain, key, vehicle)
    assert entity_id, f"no {domain} {key} for {vehicle}"
    return hass.states.get(entity_id)


def end(at: str, at_home: bool | None, distance_km: float = 8.25) -> dict[str, Any]:
    body = message("trip_end", odometer_km=20364.8)
    body["trip"] = trip(at, distance_km=distance_km, ended_at_home=at_home)
    return body


async def test_it_ends_the_trip_and_becomes_the_last_trip_without_an_event(
    hass: HomeAssistant, entry, send
) -> None:
    await send(end("2026-10-11T18:00:00Z", True))
    await send(message("trip_start", range_km=380.0))
    events = []
    for kind in (EVENT_TRIP_START, EVENT_TRIP_END, EVENT_TRIP_RESENT):
        hass.bus.async_listen(kind, events.append)

    assert await send(recovered(trip("2026-10-12T07:40:00Z"))) == 200

    assert state(hass, entry, "binary_sensor", "trip_in_progress").state == STATE_OFF
    assert state(hass, entry, "sensor", "last_trip_distance").state == "31.5"
    # the readings are not blanked by the nulls at the top
    assert state(hass, entry, "sensor", "coolant_temperature").state == "88"
    assert state(hass, entry, "sensor", "range").state == "380.0"
    # no drivepulse_trip_end hours later, nor any other event
    assert events == []


async def test_parked_at_home_follows_only_a_trip_that_becomes_the_last(
    hass: HomeAssistant, entry, send
) -> None:
    await send(end("2026-10-11T18:00:00Z", True))
    assert state(hass, entry, "binary_sensor", "parked_at_home").state == STATE_ON

    # an older recovered trip: neither the last trip nor the sensor go back
    await send(recovered(trip("2026-10-10T07:40:00Z", ended_at_home=False)))
    assert state(hass, entry, "sensor", "last_trip_distance").state == "8.25"
    assert state(hass, entry, "binary_sensor", "parked_at_home").state == STATE_ON

    # a newer one, stopped somewhere else: the sensor follows it
    await send(recovered(trip("2026-10-12T07:40:00Z", ended_at_home=False)))
    assert state(hass, entry, "binary_sensor", "parked_at_home").state == STATE_OFF

    # killed while driving: the app cannot say where the car stopped
    await send(recovered(trip("2026-10-12T09:40:00Z", ended_at_home=None)))
    assert state(hass, entry, "binary_sensor", "parked_at_home").state == STATE_UNKNOWN


async def test_an_older_one_changes_nothing_not_even_the_trip_in_progress(
    hass: HomeAssistant, entry, send
) -> None:
    await send(end("2026-10-11T18:00:00Z", True))
    await send(message("trip_start"))

    late = recovered(trip("2026-10-10T07:40:00Z", ended_at_home=False))
    assert await send(late) == 200

    # the trip in progress now is another one: it stays on
    assert state(hass, entry, "binary_sensor", "trip_in_progress").state == STATE_ON
    assert state(hass, entry, "sensor", "last_trip_distance").state == "8.25"
    assert state(hass, entry, "binary_sensor", "parked_at_home").state == STATE_ON

    # the same trip as the last one counts (>=): all of it, together
    same = recovered(trip("2026-10-11T18:00:00Z", ended_at_home=False))
    assert await send(same) == 200
    assert state(hass, entry, "binary_sensor", "trip_in_progress").state == STATE_OFF
    assert state(hass, entry, "sensor", "last_trip_distance").state == "31.5"
    assert state(hass, entry, "binary_sensor", "parked_at_home").state == STATE_OFF


async def test_a_recovered_trip_without_a_trip_is_refused(
    hass: HomeAssistant, entry, send
) -> None:
    assert await send(recovered()) == 400
    assert await send(recovered("not a trip")) == 400
    assert not dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)


async def test_a_new_home_assistant_gets_the_vehicle(
    hass: HomeAssistant, entry, send
) -> None:
    await send(recovered(trip("2026-10-12T07:40:00Z"), vehicle="Panda"))
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert [d.name for d in devices] == ["Panda"]
    last = state(hass, entry, "sensor", "last_trip_distance", "panda")
    assert last.state == "31.5"


async def test_it_survives_a_restart(
    hass: HomeAssistant, entry, send, hass_storage
) -> None:
    await send(message("trip_start"))
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()

    await send(recovered(trip("2026-10-12T07:40:00Z")))
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    saved = hass_storage[f"drivepulse.{entry.entry_id}"]["data"]["vehicles"]
    assert saved[0]["in_trip"] is False
    assert saved[0]["last_trip"]["distance_km"] == 31.5

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert state(hass, entry, "binary_sensor", "trip_in_progress").state == STATE_OFF
    assert state(hass, entry, "sensor", "last_trip_distance").state == "31.5"
