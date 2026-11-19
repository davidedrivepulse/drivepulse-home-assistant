"""Issue 6: the odometer jumped between the car's reading and the app's estimate.

On the car of the issue the car says 287006 and the app's estimate is 288119.
Up to app 3.6.2 (schema 1) `odometer_km` was the car's reading when there was
one and the estimate at a trip_end without it, so the sensor went 1,113 km
forward and back and utility_meter broke. From app 3.6.3 (schema 2) the
estimate has its own key and its own sensor.
"""

from __future__ import annotations

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.drivepulse.const import DOMAIN
from custom_components.drivepulse.hub import Vehicle

from .conftest import find, message


def _state(hass: HomeAssistant, entry, key: str):
    entity_id = find(hass, entry, "sensor", key)
    assert entity_id, key
    return hass.states.get(entity_id)


async def test_the_issue_6_sequence_keeps_two_steady_sensors(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message(schema=2, odometer_km=287006.0, odometer_estimated_km=288119.0))
    assert _state(hass, entry, "odometer").state == "287006.0"
    assert _state(hass, entry, "odometer_estimated").state == "288119.0"
    # trip_end with the adapter gone: no car reading, the estimate moved on.
    await send(
        message(
            "trip_end",
            schema=2,
            obd_connected=False,
            odometer_km=None,
            odometer_estimated_km=288131.0,
            trip={
                "id": 9,
                "start": "2026-11-15T08:40:00.000Z",
                "end": "2026-11-15T09:00:00.000Z",
                "distance_km": 12.0,
                "duration_min": 20.0,
                "avg_speed_kmh": 36.0,
                "max_speed_kmh": 70.0,
                "avg_consumption_l_100km": None,
                "odometer_km": 288131.0,
            },
        )
    )
    # The car's sensor keeps the car's last number, never the estimate.
    assert _state(hass, entry, "odometer").state == "287006.0"
    assert _state(hass, entry, "odometer_estimated").state == "288131.0"
    # A live where neither came (the app always sends both keys, null when it
    # has no number) keeps both.
    await send(message(schema=2, odometer_km=None, odometer_estimated_km=None))
    assert _state(hass, entry, "odometer").state == "287006.0"
    assert _state(hass, entry, "odometer_estimated").state == "288131.0"


async def test_the_estimate_sensor_appears_only_with_a_number(
    hass: HomeAssistant, entry, send
) -> None:
    # An app before 3.6.3 never sends the key: no empty estimate sensor.
    await send(message(odometer_km=1000.5))
    assert find(hass, entry, "sensor", "odometer_estimated") is None
    await send(message(schema=2, odometer_estimated_km=None))
    assert find(hass, entry, "sensor", "odometer_estimated") is None
    await send(message(schema=2, odometer_estimated_km=1002.0))
    entity = er.async_get(hass).async_get(find(hass, entry, "sensor", "odometer_estimated"))
    assert entity.platform == DOMAIN
    assert _state(hass, entry, "odometer_estimated").attributes["unit_of_measurement"] == "km"


async def test_the_trip_events_carry_the_estimate(
    hass: HomeAssistant, entry, send
) -> None:
    seen = []
    hass.bus.async_listen("drivepulse_trip_start", lambda e: seen.append(e.data))
    await send(message("trip_start", schema=2, odometer_estimated_km=288119.0))
    assert seen[0]["odometer_estimated_km"] == 288119.0
    assert seen[0]["odometer_km"] is None


async def test_the_last_trip_says_where_its_odometer_comes_from(
    hass: HomeAssistant, entry, send
) -> None:
    seen = []
    hass.bus.async_listen("drivepulse_trip_end", lambda e: seen.append(e.data))
    trip = {
        "id": 9,
        "start": "2026-11-15T08:40:00.000Z",
        "end": "2026-11-15T09:00:00.000Z",
        "distance_km": 12.0,
        "duration_min": 20.0,
        "avg_speed_kmh": 36.0,
        "max_speed_kmh": 70.0,
        "avg_consumption_l_100km": None,
        "odometer_km": 288131.0,
        "odometer_source": "app",
    }
    await send(message("trip_end", schema=2, odometer_estimated_km=288131.0, trip=trip))
    last = _state(hass, entry, "last_trip_distance")
    assert last.attributes["odometer_km"] == 288131.0
    assert last.attributes["odometer_source"] == "app"
    assert seen[0]["trip"]["odometer_source"] == "app"


async def _restart(hass: HomeAssistant, entry) -> None:
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_a_car_that_never_gives_it_drops_the_old_estimate_at_schema_2(
    hass: HomeAssistant, entry, send
) -> None:
    # App 3.6.2 (schema 1): at trip_end odometer_km was the app's estimate.
    await send(message("trip_end", odometer_km=288119.0))
    assert _state(hass, entry, "odometer").state == "288119.0"
    # App 3.6.3 (schema 2): the car gives nothing, the estimate has its key.
    await send(message(schema=2, odometer_km=None, odometer_estimated_km=288131.0))
    assert _state(hass, entry, "odometer").state == STATE_UNAVAILABLE, (
        "god 19/11: never the old estimate held as Odometer"
    )
    assert _state(hass, entry, "odometer_estimated").state == "288131.0"
    # A car reading from schema 2 on is kept as before.
    await send(message(schema=2, odometer_km=287010.0))
    await send(message(schema=2, odometer_km=None))
    assert _state(hass, entry, "odometer").state == "287010.0"


async def test_the_schema_1_value_is_dropped_after_a_restart_too(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message("trip_end", odometer_km=288119.0))
    await _restart(hass, entry)
    assert _state(hass, entry, "odometer").state == "288119.0"
    await send(message(schema=2, odometer_km=None))
    assert _state(hass, entry, "odometer").state == STATE_UNAVAILABLE


async def test_a_schema_2_reading_survives_a_restart(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message(schema=2, odometer_km=287006.0))
    await _restart(hass, entry)
    await send(message(schema=2, odometer_km=None))
    assert _state(hass, entry, "odometer").state == "287006.0"


def test_a_value_kept_by_0_2_is_taken_as_schema_1() -> None:
    old = Vehicle.from_dict({"name": "My car", "values": {"odometer": 288119.0}})
    assert old.odometer_schema == 1
    assert Vehicle.from_dict({"name": "My car", "values": {}}).odometer_schema is None
    new = Vehicle.from_dict(
        {"name": "My car", "values": {"odometer": 1.0}, "odometer_schema": 2}
    )
    assert new.odometer_schema == 2


async def test_the_estimate_is_a_total_that_can_go_down(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message(schema=2, odometer_estimated_km=288131.0))
    state = _state(hass, entry, "odometer_estimated")
    assert state.attributes["state_class"] == "total"
    await send(message(schema=2, odometer_estimated_km=288100.0))
    assert _state(hass, entry, "odometer_estimated").state == "288100.0"
