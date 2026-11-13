"""A custom PID standing in for a built-in sensor, set up in the options."""

from __future__ import annotations

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.drivepulse.const import (
    CONF_LOCAL_ONLY,
    CONF_SOURCES,
    EVENT_TRIP_END,
)
from custom_components.drivepulse.sensor import DESCRIPTIONS
from custom_components.drivepulse.units import SOURCE_UNITS

from .conftest import find, message

AT = "2026-10-10T08:00:00.000Z"
SOC = {"name": "SoC", "value": 80.4, "unit": "%", "at": AT}
VOLT = {"name": "12V", "value": 14100, "unit": "mV", "at": AT}
OIL = {"name": "Oil", "value": 64, "unit": "°C", "at": AT}


def state(hass: HomeAssistant, entry, key: str, vehicle: str = "my_car"):
    entity_id = find(hass, entry, "sensor", key, vehicle)
    assert entity_id, key
    return hass.states.get(entity_id)


async def open_sources(hass: HomeAssistant, entry):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "sources"}
    )


async def choose(hass: HomeAssistant, entry, flow_id: str, choice: dict):
    result = await hass.config_entries.options.async_configure(flow_id, choice)
    await hass.async_block_till_done()
    return result


def test_the_units_are_the_sensors_units() -> None:
    for key, unit in SOURCE_UNITS.items():
        assert DESCRIPTIONS[key].native_unit_of_measurement == unit, key


async def test_no_custom_pid_yet(hass: HomeAssistant, entry, send) -> None:
    await send(message())
    result = await open_sources(hass, entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_custom_pids"


async def test_a_custom_pid_replaces_a_zero_reading(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message(hv_soc_pct=0, custom={"cp1": SOC}))
    assert state(hass, entry, "battery_level").state == "0"

    result = await open_sources(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "vehicle_sources"
    assert result["description_placeholders"] == {"vehicle": "My car"}
    result = await choose(hass, entry, result["flow_id"], {"battery_level": "cp1"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    # The other options are kept.
    assert entry.options == {CONF_SOURCES: {"my_car": {"battery_level": "cp1"}}}

    ends = async_capture_events(hass, EVENT_TRIP_END)
    await send(message("trip_end", hv_soc_pct=0, custom={"cp1": SOC}))
    battery = state(hass, entry, "battery_level")
    assert battery.state == "80.4"
    assert battery.attributes["source_pid"] == "cp1"
    assert battery.attributes["device_class"] == "battery"
    assert ends[0].data["hv_soc_pct"] == 80.4
    # The custom PID's own sensor is still there.
    assert state(hass, entry, "custom_cp1").state == "80.4"

    # No reading of the PID: the sensor says so, not the app's 0.
    await send(message(hv_soc_pct=0, custom={}))
    assert state(hass, entry, "battery_level").state == STATE_UNAVAILABLE


async def test_the_unit_is_converted(hass: HomeAssistant, entry, send) -> None:
    await send(message(custom={"cp2": VOLT}))
    result = await open_sources(hass, entry)
    await choose(hass, entry, result["flow_id"], {"battery_voltage": "cp2"})
    await send(message(battery_voltage=0, custom={"cp2": VOLT}))
    assert state(hass, entry, "battery_voltage").state == "14.1"


async def test_a_unit_of_another_kind_is_refused(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message(custom={"cp3": OIL}))
    result = await open_sources(hass, entry)
    result = await choose(hass, entry, result["flow_id"], {"battery_level": "cp3"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"battery_level": "wrong_unit"}
    # The same PID fits the coolant.
    result = await choose(
        hass, entry, result["flow_id"], {"coolant_temperature": "cp3"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_an_empty_field_goes_back_to_the_app(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message(custom={"cp1": SOC}))
    result = await open_sources(hass, entry)
    await choose(hass, entry, result["flow_id"], {"battery_level": "cp1"})
    result = await open_sources(hass, entry)
    await choose(hass, entry, result["flow_id"], {})
    assert entry.options == {CONF_SOURCES: {}}
    await send(message(hv_soc_pct=55, custom={"cp1": SOC}))
    assert state(hass, entry, "battery_level").state == "55"
    assert "source_pid" not in state(hass, entry, "battery_level").attributes


async def test_pick_the_vehicle_first(hass: HomeAssistant, entry, send) -> None:
    await send(message(custom={"cp1": SOC}))
    await send(message(vehicle="Van", custom={"cp1": OIL}))
    await send(message(vehicle="Bike"))  # no custom PID: not offered
    result = await open_sources(hass, entry)
    assert result["step_id"] == "sources"
    options = result["data_schema"].schema["vehicle"].config["options"]
    assert [o["label"] for o in options] == ["My car", "Van"]
    result = await choose(hass, entry, result["flow_id"], {"vehicle": "van"})
    assert result["step_id"] == "vehicle_sources"
    result = await choose(hass, entry, result["flow_id"], {"coolant_temperature": "cp1"})
    assert entry.options[CONF_SOURCES] == {"van": {"coolant_temperature": "cp1"}}
    await send(message(vehicle="Van", coolant_temp_c=0, custom={"cp1": OIL}))
    assert state(hass, entry, "coolant_temperature", "van").state == "64"
    # The other vehicle keeps the app's reading.
    await send(message(coolant_temp_c=88, custom={"cp1": SOC}))
    assert state(hass, entry, "coolant_temperature").state == "88"


async def test_the_network_switch_keeps_the_sources(
    hass: HomeAssistant, entry, send
) -> None:
    await send(message(custom={"cp1": SOC}))
    result = await open_sources(hass, entry)
    await choose(hass, entry, result["flow_id"], {"battery_level": "cp1"})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "network"}
    )
    await choose(hass, entry, result["flow_id"], {CONF_LOCAL_ONLY: False})
    assert entry.options == {
        CONF_LOCAL_ONLY: False,
        CONF_SOURCES: {"my_car": {"battery_level": "cp1"}},
    }


async def test_broken_options_are_ignored(hass: HomeAssistant, entry, send) -> None:
    hass.config_entries.async_update_entry(
        entry,
        options={
            CONF_SOURCES: {
                "my_car": {"trouble_codes": "cp1", "battery_level": "x; drop"},
                "van": "cp1",
            }
        },
    )
    await hass.async_block_till_done()
    assert await send(message(hv_soc_pct=55, custom={"cp1": SOC})) == 200
    assert state(hass, entry, "battery_level").state == "55"
