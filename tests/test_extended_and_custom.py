"""Readings of `extended`, and the custom PIDs of `custom`."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.drivepulse.const import EVENT_TRIP_END, EVENT_TRIP_START
from custom_components.drivepulse.hub import MAX_CUSTOM

from .conftest import find, message

APP = json.loads(
    (Path(__file__).parent / "schema1_app_messages.json").read_text(encoding="utf-8")
)
OIL = {"name": "Oil", "value": 64, "unit": "°C", "at": "2026-10-10T08:00:00.000Z"}


def state(hass: HomeAssistant, entry, domain: str, key: str):
    entity_id = find(hass, entry, domain, key)
    assert entity_id, f"no {domain} {key}"
    return hass.states.get(entity_id)


# -- extended ----------------------------------------------------------------


async def test_extended_readings_become_sensors(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message(extended={"oil_temp_c": 95, "hv_soh_pct": 96.7}))
    oil = state(hass, entry, "sensor", "oil_temperature")
    assert oil.state == "95"
    assert oil.attributes["device_class"] == "temperature"
    assert oil.attributes["unit_of_measurement"] == "°C"
    assert state(hass, entry, "sensor", "hv_battery_health").state == "96.7"
    # Not sent: no sensor at all.
    assert find(hass, entry, "sensor", "adblue_level") is None


async def test_the_whole_app_message_is_taken(hass: HomeAssistant, entry, send) -> None:
    assert await send(APP["live tutto"]) == 200
    vehicle = "auto_di_prova"
    for key in ("oil_temperature", "dpf_load", "gearbox_temperature", "torque"):
        assert find(hass, entry, "sensor", key, vehicle), key
    assert find(hass, entry, "binary_sensor", "dpf_regenerating", vehicle)
    # The duplicates of the top-level keys are not a second sensor.
    unique_ids = {
        e.unique_id
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    }
    assert not any(u.endswith(("_hv_soc_pct", "_odometer_km")) for u in unique_ids)


async def test_fast_readings_are_disabled_by_default(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message(extended={"engine_load_pct": 40}))
    entity_id = find(hass, entry, "sensor", "engine_load")
    assert entity_id
    assert er.async_get(hass).async_get(entity_id).disabled_by is not None


async def test_a_reading_missing_from_extended_is_unavailable(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message(extended={"oil_temp_c": 95, "adblue_level_pct": 77.8}))
    await send(message(extended={}))
    assert state(hass, entry, "sensor", "oil_temperature").state == STATE_UNAVAILABLE
    # Slow readings keep their last value while the adapter is away.
    assert state(hass, entry, "sensor", "adblue_level").state == "77.8"
    # No `extended` at all (an older app): no change.
    await send(message(extended={"oil_temp_c": 90}))
    payload = message()
    del payload["extended"]
    await send(payload)
    assert state(hass, entry, "sensor", "oil_temperature").state == "90"


async def test_dpf_regeneration(hass: HomeAssistant, entry, send) -> None:
    assert find(hass, entry, "binary_sensor", "dpf_regenerating") is None
    await send(message(extended={"dpf_regen_active": True}))
    assert state(hass, entry, "binary_sensor", "dpf_regenerating").state == STATE_ON
    await send(message(extended={"dpf_regen_active": False}))
    assert state(hass, entry, "binary_sensor", "dpf_regenerating").state == STATE_OFF
    await send(message(extended={}))
    assert (
        state(hass, entry, "binary_sensor", "dpf_regenerating").state
        == STATE_UNAVAILABLE
    )


# -- custom PIDs -------------------------------------------------------------


async def test_a_custom_pid_becomes_a_sensor(hass: HomeAssistant, entry, send) -> None:
    await send(message(custom={"cp3": OIL}))
    oil = state(hass, entry, "sensor", "custom_cp3")
    assert oil.entity_id == "sensor.my_car_oil"
    assert oil.state == "64"
    assert oil.attributes["friendly_name"] == "My car Oil"
    assert oil.attributes["device_class"] == "temperature"
    assert oil.attributes["unit_of_measurement"] == "°C"
    assert oil.attributes["state_class"] == "measurement"
    assert oil.attributes["pid"] == "cp3"
    assert oil.attributes["measured_at"] == OIL["at"]


async def test_an_unknown_unit_is_kept_without_device_class(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message(custom={"cp1": {**OIL, "name": "SoC", "unit": "%"}}))
    soc = state(hass, entry, "sensor", "custom_cp1")
    assert soc.attributes["unit_of_measurement"] == "%"
    assert "device_class" not in soc.attributes
    await send(message(custom={"cp1": {**OIL, "name": "Boost", "unit": "lbf/sq"}}))
    assert state(hass, entry, "sensor", "custom_cp1").attributes[
        "unit_of_measurement"
    ] == "lbf/sq"


async def test_rename_and_new_unit_follow_the_app(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message(custom={"cp4": {**OIL, "name": "Boost", "unit": "mbar"}}))
    entity_id = find(hass, entry, "sensor", "custom_cp4")
    await send(
        message(custom={"cp4": {**OIL, "name": "Turbo", "value": 33.5, "unit": "kPa"}})
    )
    # Same entity, same entity id and history; new name and unit.
    assert find(hass, entry, "sensor", "custom_cp4") == entity_id
    turbo = hass.states.get(entity_id)
    assert turbo.attributes["friendly_name"] == "My car Turbo"
    assert turbo.attributes["unit_of_measurement"] == "kPa"
    assert turbo.attributes["device_class"] == "pressure"
    assert turbo.state == "33.5"


async def test_a_pid_missing_from_custom_is_unavailable(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message(custom={"cp3": OIL}))
    await send(message(custom={}))
    oil = state(hass, entry, "sensor", "custom_cp3")
    assert oil.state == STATE_UNAVAILABLE
    # No `custom` at all (an app before 3.5.9): no change.
    await send(message(custom={"cp3": OIL}))
    await send(message())
    assert state(hass, entry, "sensor", "custom_cp3").state == "64"


async def test_bad_custom_entries_are_ignored(hass: HomeAssistant, entry, send) -> None:
    bad = {
        "cp5": {**OIL, "value": None},  # never a number: no sensor
        "cp6": {**OIL, "value": "64"},
        "x7": OIL,
        "cp8; drop": OIL,
        "cp9": "64",
    }
    assert await send(message(custom=bad)) == 200
    unique_ids = {
        e.unique_id
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    }
    assert not any("custom" in u for u in unique_ids)
    assert await send(message(custom=[1, 2])) == 200


async def test_custom_pids_are_limited(hass: HomeAssistant, entry, send) -> None:
    many = {f"cp{i}": OIL for i in range(MAX_CUSTOM + 10)}
    await send(message(custom=many))
    found = [
        e
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if "_custom_" in e.unique_id
    ]
    assert len(found) == MAX_CUSTOM


async def test_custom_pids_come_back_after_a_restart(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message(custom={"cp3": OIL}))
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    oil = state(hass, entry, "sensor", "custom_cp3")
    assert oil.state == STATE_UNAVAILABLE  # the reading comes with the next message
    assert oil.attributes["friendly_name"] == "My car Oil"
    await send(message(custom={"cp3": OIL}))
    assert state(hass, entry, "sensor", "custom_cp3").state == "64"


async def test_custom_pids_are_in_the_trip_events(
    hass: HomeAssistant, entry, send
) -> None:
    starts = async_capture_events(hass, EVENT_TRIP_START)
    ends = async_capture_events(hass, EVENT_TRIP_END)
    await send(message("trip_start"))
    assert starts[0].data["custom"] == {}
    await send(message("live", custom={"cp3": OIL, "cp4": {**OIL, "name": "Boost"}}))
    await send(message("trip_end", custom={"cp3": OIL}))
    assert ends[0].data["custom"] == {
        "cp3": {"name": "Oil", "value": 64, "unit": "°C"},
        "cp4": {"name": "Boost", "value": None, "unit": "°C"},
    }
