"""trip_discarded: the trip that had just started was a false start.

The app opens a trip and sends trip_start at once (the car leaving is what
automations wait for). When the trip ends with fewer than 5 GPS points the
app deletes it, and no trip_end will ever come: without this message, Trip
in progress stayed on until the next trip.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.const import STATE_OFF, STATE_ON
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


def discarded(**fields: Any) -> dict[str, Any]:
    """Shaped like the app's: the last values read, trip_km 0, no trip."""
    return message(
        "trip_discarded",
        obd_connected=False,
        rpm=None,
        speed_kmh=None,
        trip_km=0,
        **fields,
    )


def state(hass: HomeAssistant, entry, domain: str, key: str, vehicle: str = "my_car"):
    entity_id = find(hass, entry, domain, key, vehicle)
    assert entity_id, f"no {domain} {key} for {vehicle}"
    return hass.states.get(entity_id)


def end_at_home() -> dict[str, Any]:
    body = message("trip_end", odometer_km=20364.8)
    body["trip"] = {
        "id": 3,
        "start": "2026-10-09T07:00:00Z",
        "end": "2026-10-09T07:12:00Z",
        "distance_km": 8.25,
        "duration_min": 12.0,
        "avg_speed_kmh": 41.3,
        "max_speed_kmh": 70.0,
        "avg_consumption_l_100km": 5.9,
        "odometer_km": 20364.8,
        "ended_at_home": True,
    }
    return body


async def test_it_turns_trip_in_progress_off_and_nothing_else(
    hass: HomeAssistant, entry, send
) -> None:
    await send(end_at_home())
    await send(message("trip_start", range_km=380.0))
    assert state(hass, entry, "binary_sensor", "trip_in_progress").state == STATE_ON
    events = []
    for kind in (EVENT_TRIP_START, EVENT_TRIP_END, EVENT_TRIP_RESENT):
        hass.bus.async_listen(kind, events.append)

    # values that differ from the ones Home Assistant has: none may land
    assert await send(discarded(coolant_temp_c=40, range_km=12.0)) == 200

    assert state(hass, entry, "binary_sensor", "trip_in_progress").state == STATE_OFF
    # no reading, no adapter flag
    assert state(hass, entry, "sensor", "coolant_temperature").state == "88"
    assert state(hass, entry, "sensor", "range").state == "380.0"
    assert state(hass, entry, "binary_sensor", "adapter_connected").state == STATE_ON
    # the last trip and Parked at home stay the ones of the last real trip
    assert state(hass, entry, "sensor", "last_trip_distance").state == "8.25"
    assert state(hass, entry, "binary_sensor", "parked_at_home").state == STATE_ON
    # no drivepulse_trip_end: "the car arrived" did not happen
    assert events == []


async def test_without_a_trip_in_progress_it_changes_nothing(
    hass: HomeAssistant, entry, send
) -> None:
    await send(end_at_home())
    assert await send(discarded(coolant_temp_c=40)) == 200
    assert state(hass, entry, "binary_sensor", "trip_in_progress").state == STATE_OFF
    assert state(hass, entry, "sensor", "coolant_temperature").state == "88"


async def test_an_unknown_vehicle_is_not_created(
    hass: HomeAssistant, entry, send
) -> None:
    assert await send(discarded(vehicle="Panda")) == 200
    assert await send(discarded(vehicle=None)) == 200
    assert not dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)


async def test_only_the_vehicle_of_the_message(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message("trip_start"))
    await send(message("trip_start", vehicle="Panda"))
    await send(discarded(vehicle="Panda"))
    assert (
        state(hass, entry, "binary_sensor", "trip_in_progress", "panda").state
        == STATE_OFF
    )
    assert state(hass, entry, "binary_sensor", "trip_in_progress").state == STATE_ON


async def test_off_survives_a_restart(
    hass: HomeAssistant, entry, send, hass_storage
) -> None:
    await send(message("trip_start"))
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    saved = hass_storage[f"drivepulse.{entry.entry_id}"]["data"]["vehicles"]
    assert saved[0]["in_trip"] is True, "premise: the trip_start is on disk"

    await send(discarded())
    # saved on its own, not only when Home Assistant stops cleanly
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    saved = hass_storage[f"drivepulse.{entry.entry_id}"]["data"]["vehicles"]
    assert saved[0]["in_trip"] is False

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert state(hass, entry, "binary_sensor", "trip_in_progress").state == STATE_OFF
