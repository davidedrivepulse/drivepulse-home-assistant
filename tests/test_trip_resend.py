"""trip_resend: a saved trip the user sends again by hand from the app."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.drivepulse.const import (
    EVENT_TRIP_END,
    EVENT_TRIP_RESENT,
    EVENT_TRIP_START,
    MAX_VEHICLES,
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


def trip(end: str | None, **fields: Any) -> dict[str, Any]:
    return {
        "id": 3,
        "start": "2026-10-09T07:00:00Z",
        "end": end,
        "distance_km": 8.25,
        "duration_min": 12.0,
        "avg_speed_kmh": 41.3,
        "max_speed_kmh": 70.0,
        "avg_consumption_l_100km": 5.9,
        "odometer_km": 20100.4,
        **fields,
    }


def resend(the_trip: Any = None, **fields: Any) -> dict[str, Any]:
    """Shaped like the app's trip_resend: every reading null, the trip apart."""
    body = message("trip_resend", obd_connected=False, **NULLS, **fields)
    if the_trip is not None:
        body["trip"] = the_trip
    return body


def state(hass: HomeAssistant, entry, domain: str, key: str, vehicle: str = "my_car"):
    entity_id = find(hass, entry, domain, key, vehicle)
    assert entity_id, f"no {domain} {key} for {vehicle}"
    return hass.states.get(entity_id)


async def test_a_resend_changes_no_reading_and_no_trip_in_progress(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message("trip_end", odometer_km=20364.8, dtc_count=2, dtc=["P0420"]))
    await send(message("trip_start", range_km=380.0))
    events = []
    for kind in (EVENT_TRIP_START, EVENT_TRIP_END, EVENT_TRIP_RESENT):
        hass.bus.async_listen(kind, events.append)

    assert await send(resend(trip("2026-10-12T08:00:00Z"))) == 200

    # the readings of the car now are not blanked by the nulls of a resend
    assert state(hass, entry, "sensor", "coolant_temperature").state == "88"
    assert state(hass, entry, "sensor", "battery_voltage").state == "14.1"
    assert state(hass, entry, "sensor", "odometer").state == "20364.8"
    assert state(hass, entry, "sensor", "trouble_codes").state == "2"
    assert state(hass, entry, "sensor", "range").state == "380.0"
    # the adapter is still connected and the trip in progress goes on
    assert state(hass, entry, "binary_sensor", "adapter_connected").state == STATE_ON
    assert state(hass, entry, "binary_sensor", "trip_in_progress").state == STATE_ON
    # only drivepulse_trip_resent, never a trip_end for a trip of the past
    assert [e.event_type for e in events] == [EVENT_TRIP_RESENT]


async def test_the_event_carries_the_trip_and_nothing_else(
    hass: HomeAssistant, entry, send
) -> None:
    events = []
    hass.bus.async_listen(EVENT_TRIP_RESENT, events.append)
    await send(resend(trip("2026-10-09T07:12:00Z", route="secret", vin="X")))

    data = events[0].data
    assert set(data) == {"device_id", "vehicle", "sent_at", "trip"}
    assert data["vehicle"] == "My car"
    assert data["device_id"]
    assert data["sent_at"] == "2026-10-11T00:41:59.418857Z"
    assert data["trip"]["distance_km"] == 8.25
    assert data["trip"]["end"] == "2026-10-09T07:12:00Z"
    assert not {"id", "route", "vin"} & set(data["trip"])


async def test_an_older_trip_does_not_replace_the_last_trip(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message("trip_end", trip=trip("2026-10-10T07:12:00Z", distance_km=20.0)))
    events = []
    hass.bus.async_listen(EVENT_TRIP_RESENT, events.append)

    await send(resend(trip("2026-10-09T07:12:00Z", distance_km=8.25)))
    assert state(hass, entry, "sensor", "last_trip_distance").state == "20.0"
    # the event still goes out: an automation can log the old trip
    assert events[-1].data["trip"]["distance_km"] == 8.25

    # the same trip sent again after a correction brings the corrected value
    await send(resend(trip("2026-10-10T07:12:00Z", distance_km=20.5)))
    assert state(hass, entry, "sensor", "last_trip_distance").state == "20.5"

    await send(resend(trip("2026-10-11T07:12:00Z", distance_km=31.5)))
    assert state(hass, entry, "sensor", "last_trip_distance").state == "31.5"


async def test_a_trip_without_an_end_is_dated_by_its_start(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message("trip_end", trip=trip("2026-10-10T07:12:00Z", distance_km=20.0)))
    # started after the last trip ended: more recent, even without an end
    await send(resend(trip(None, start="2026-10-10T09:00:00Z", distance_km=4.5)))
    assert state(hass, entry, "sensor", "last_trip_distance").state == "4.5"
    # no time at all: it cannot be placed, the last trip stays
    await send(resend(trip(None, start="not a time", distance_km=7.0)))
    assert state(hass, entry, "sensor", "last_trip_distance").state == "4.5"


async def test_a_resend_to_a_new_home_assistant_creates_the_vehicle(
    hass: HomeAssistant, entry, send
) -> None:
    await send(resend(trip("2026-10-09T07:12:00Z"), vehicle="Panda"))
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert [d.name for d in devices] == ["Panda"]
    last = state(hass, entry, "sensor", "last_trip_distance", "panda")
    assert last.state == "8.25"
    # no reading came with it: the sensors wait for the car
    assert (
        state(hass, entry, "sensor", "battery_voltage", "panda").state
        == STATE_UNAVAILABLE
    )


async def test_the_last_trip_of_a_resend_survives_a_restart(
    hass: HomeAssistant, entry, send, hass_storage
) -> None:
    await send(resend(trip("2026-10-09T07:12:00Z")))
    # saved on its own, not only when Home Assistant stops cleanly
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    saved = hass_storage[f"drivepulse.{entry.entry_id}"]["data"]["vehicles"]
    assert saved[0]["last_trip"]["distance_km"] == 8.25

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert state(hass, entry, "sensor", "last_trip_distance").state == "8.25"


async def test_a_resend_without_a_trip_is_refused_and_creates_nothing(
    hass: HomeAssistant, entry, send
) -> None:
    events = []
    hass.bus.async_listen(EVENT_TRIP_RESENT, events.append)
    assert await send(resend()) == 400
    assert await send(resend("not a trip")) == 400
    assert not dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert not events


async def test_a_resend_without_a_name_goes_to_the_default_vehicle(
    hass: HomeAssistant, entry, send
) -> None:
    await send(resend(trip("2026-10-09T07:12:00Z"), vehicle=None))
    names = [
        d.name
        for d in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    ]
    assert names == ["DrivePulse"]


async def test_a_resend_respects_the_vehicle_limit(
    hass: HomeAssistant, entry, send
) -> None:
    for i in range(MAX_VEHICLES):
        assert await send(message(vehicle=f"Car {i}")) == 200
    events = []
    hass.bus.async_listen(EVENT_TRIP_RESENT, events.append)
    assert (
        await send(resend(trip("2026-10-09T07:12:00Z"), vehicle="One too many")) == 400
    )
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert len(devices) == MAX_VEHICLES
    assert not events
