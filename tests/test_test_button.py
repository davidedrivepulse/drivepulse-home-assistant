"""The app's "Test send" button: the device appears, nothing else changes."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
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


def state(hass: HomeAssistant, entry, domain: str, key: str, vehicle: str = "my_car"):
    entity_id = find(hass, entry, domain, key, vehicle)
    assert entity_id, f"no {domain} {key} for {vehicle}"
    return hass.states.get(entity_id)


def listen(hass: HomeAssistant) -> list:
    events: list = []
    for kind in (EVENT_TRIP_START, EVENT_TRIP_END, EVENT_TRIP_RESENT):
        hass.bus.async_listen(kind, events.append)
    return events


def devices(hass: HomeAssistant, entry) -> list[str]:
    return sorted(
        d.name
        for d in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    )


async def test_a_test_creates_the_device_and_its_entities_without_values(
    hass: HomeAssistant, entry, send
) -> None:
    events = listen(hass)
    # the app's test with the adapter connected carries real readings
    assert await send(message("test", odometer_km=1000.5, dtc_count=1)) == 200

    assert devices(hass, entry) == ["My car"]
    for key in ("battery_voltage", "coolant_temperature", "odometer", "trouble_codes"):
        assert state(hass, entry, "sensor", key).state == STATE_UNAVAILABLE, key
    assert state(hass, entry, "sensor", "last_trip_distance").state == STATE_UNAVAILABLE
    assert state(hass, entry, "binary_sensor", "trip_in_progress").state == STATE_OFF
    assert state(hass, entry, "binary_sensor", "adapter_connected").state != STATE_ON
    # a fuel level in the test does not create the fuel sensor either
    assert find(hass, entry, "sensor", "fuel_level") is None
    assert not events


async def test_a_test_changes_nothing_on_a_known_vehicle(
    hass: HomeAssistant, entry, send
) -> None:
    trip = {"start": "2026-10-11T00:41:09Z", "end": "2026-10-11T00:55:09Z"}
    await send(
        message("trip_end", odometer_km=20364.8, trip={**trip, "distance_km": 12.5})
    )
    await send(message("trip_start", range_km=380.0))
    events = listen(hass)

    await send(
        message(
            "test",
            obd_connected=False,
            coolant_temp_c=None,
            battery_voltage=12.0,
            odometer_km=1.0,
            range_km=None,
            trip={**trip, "distance_km": 99.0},
        )
    )

    assert state(hass, entry, "sensor", "coolant_temperature").state == "88"
    assert state(hass, entry, "sensor", "battery_voltage").state == "14.1"
    assert state(hass, entry, "sensor", "odometer").state == "20364.8"
    assert state(hass, entry, "sensor", "range").state == "380.0"
    assert state(hass, entry, "sensor", "last_trip_distance").state == "12.5"
    assert state(hass, entry, "binary_sensor", "adapter_connected").state == STATE_ON
    assert state(hass, entry, "binary_sensor", "trip_in_progress").state == STATE_ON
    assert not events


async def test_a_test_without_a_name_goes_to_the_default_vehicle(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message("test", vehicle=None))
    await send(message("test", vehicle="   "))
    assert devices(hass, entry) == ["DrivePulse"]


async def test_a_test_respects_the_vehicle_limit(
    hass: HomeAssistant, entry, send
) -> None:
    for i in range(MAX_VEHICLES):
        assert await send(message("test", vehicle=f"Car {i}")) == 200
    assert await send(message("test", vehicle="One too many")) == 400
    assert len(devices(hass, entry)) == MAX_VEHICLES
    # a vehicle already there still answers 200
    assert await send(message("test", vehicle="Car 0")) == 200


async def test_the_vehicle_of_a_test_is_kept(
    hass: HomeAssistant, entry, send, hass_storage
) -> None:
    await send(message("test", vehicle="Panda"))
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    saved = hass_storage[f"drivepulse.{entry.entry_id}"]["data"]["vehicles"]
    assert [v["name"] for v in saved] == ["Panda"]
    assert saved[0]["values"] == {} and saved[0]["last_trip"] is None
