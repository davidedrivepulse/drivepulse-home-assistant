"""Issue 6: the odometer jumped between the car's reading and the app's estimate.

On the car of the issue the car says 287006 and the app's estimate is 288119.
Up to app 3.6.2 (schema 1) `odometer_km` was the car's reading when there was
one and the estimate at a trip_end without it, so the sensor went 1,113 km
forward and back and utility_meter broke. From app 3.6.3 (schema 2) the
estimate has its own key and its own sensor.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.drivepulse.const import DOMAIN

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
