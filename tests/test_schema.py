"""schema/drivepulse-schema-1.json describes what the app sends, and what this
integration reads."""

from __future__ import annotations

import copy
import json
import pathlib

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from custom_components.drivepulse.const import KNOWN_MESSAGES
from custom_components.drivepulse.hub import (
    EVENT_FIELDS,
    NUMERIC_KEYS,
    TRIP_AT_HOME,
    TRIP_FIELDS,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = json.loads(
    (ROOT / "schema/drivepulse-schema-1.json").read_text(encoding="utf-8")
)
# Messages built by the app's own code (PayloadWebhook in the DrivePulse app,
# made-up values), one per kind of message.
APP_MESSAGES = json.loads(
    (ROOT / "tests/schema1_app_messages.json").read_text(encoding="utf-8")
)
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())

NULLABLE = [
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
]
TEST = {
    "source": "drivepulse",
    "schema": 1,
    "event": "test",
    "sent_at": "2026-10-10T08:00:00.000Z",
    "units": "metric",
    "vehicle": None,
    "obd_connected": False,
    "obd_at": None,
    **{key: None for key in NULLABLE},
    "extended": {},
    "custom": {},
}
LIVE = {
    **TEST,
    "event": "live",
    "vehicle": "My car",
    "obd_connected": True,
    "obd_at": "2026-10-10T08:00:00.000Z",
    "rpm": 2100,
    "speed_kmh": 64,
    "coolant_temp_c": 90,
    "battery_voltage": 14.23,
    "fuel_level_pct": 63.0,
    "throttle_pct": 18.0,
    "consumption_l_100km": 6.6,
    "trip_km": 3.14,
    "dtc_count": 2,
    "dtc": ["P0420", "P0171"],
    "extended": {"oil_temp_c": 95, "fuel_rate_lh": 4.2, "dpf_regen_active": False},
    "custom": {
        "cp3": {
            "name": "Oil",
            "value": 64,
            "unit": "°C",
            "at": "2026-10-10T07:59:58.000Z",
        }
    },
}
TRIP = {
    "id": 7,
    "start": "2026-10-10T07:00:00.000Z",
    "end": "2026-10-10T07:30:00.000Z",
    "distance_km": 21.46,
    "duration_min": 30.0,
    "avg_speed_kmh": 42.9,
    "max_speed_kmh": 110.0,
    "avg_consumption_l_100km": 6.0,
    "odometer_km": None,
}
TRIP_END = {**TEST, "event": "trip_end", "trip_km": 21.46, "trip": TRIP}
# A saved trip sent again by hand: the trip apart, every reading null.
TRIP_RESEND = {**TEST, "event": "trip_resend", "vehicle": "My car", "trip": TRIP}


def _errors(message: dict) -> list[str]:
    return [error.message for error in VALIDATOR.iter_errors(message)]


def test_the_schema_is_a_valid_draft_2020_12_schema() -> None:
    Draft202012Validator.check_schema(SCHEMA)


def test_the_events_are_the_messages_the_integration_knows() -> None:
    assert set(SCHEMA["properties"]["event"]["enum"]) == KNOWN_MESSAGES


def test_every_key_the_integration_reads_is_in_the_schema() -> None:
    top = SCHEMA["properties"]
    for key in [*NUMERIC_KEYS, *EVENT_FIELDS]:
        assert key in top, key
        assert key in SCHEMA["required"], key
    assert set(top["trip"]["properties"]) == set(TRIP_FIELDS) | {"id", TRIP_AT_HOME}


def test_no_position_no_address_no_vin() -> None:
    def keys(node: object) -> set[str]:
        if not isinstance(node, dict):
            return set()
        found = set(node.get("properties", {}))
        for value in node.values():
            found |= keys(value)
        return found

    words = {"lat", "lon", "latitude", "longitude", "gps", "position"}
    words |= {"address", "place", "route", "vin"}
    found = keys(SCHEMA)
    assert found, "no keys found: the walk is broken"
    assert not [k for k in found if words & set(k.lower().split("_"))]


def test_the_schema_has_exactly_the_keys_the_app_sends() -> None:
    # The schema is open (a newer app can add keys, and a receiver keeps an
    # old copy of this file), so a key added to the app without the schema,
    # or a position, an address or the VIN, is caught here: the keys of the
    # messages the app really builds must be the schema's, at the top, in
    # `extended` and in `trip`.
    top: set[str] = set()
    extended: set[str] = set()
    trip: set[str] = set()
    for message in APP_MESSAGES.values():
        top |= set(message)
        extended |= set(message.get("extended") or {})
        trip |= set(message.get("trip") or {})
    properties = SCHEMA["properties"]
    assert top == set(properties)
    assert extended == set(properties["extended"]["properties"])
    assert trip == set(properties["trip"]["properties"])


def test_a_newer_app_with_more_keys_is_still_valid() -> None:
    newer = copy.deepcopy(TRIP_END)
    newer["new_top_key"] = 1
    newer["extended"]["new_reading"] = 2.0
    newer["trip"]["new_trip_key"] = 3
    assert _errors(newer) == []


@pytest.mark.parametrize("name", sorted(APP_MESSAGES))
def test_the_messages_the_app_builds_are_valid(name: str) -> None:
    assert _errors(APP_MESSAGES[name]) == []


def test_the_app_messages_cover_every_event() -> None:
    assert {m["event"] for m in APP_MESSAGES.values()} == KNOWN_MESSAGES


def test_electric_trip_end_and_an_app_without_custom_are_valid() -> None:
    electric = copy.deepcopy(TRIP_END)
    del electric["trip"]["avg_consumption_l_100km"]
    electric["trip"]["avg_consumption_kwh_100km"] = 16.0
    assert _errors(electric) == []
    # App 3.5.6 to 3.5.8: no `custom` yet.
    assert _errors({k: v for k, v in LIVE.items() if k != "custom"}) == []
    assert _errors(LIVE) == []
    assert _errors(TRIP_END) == []
    assert _errors(TRIP_RESEND) == []


def test_ended_at_home_is_a_yes_a_no_or_null_and_may_be_missing() -> None:
    # Missing: an app from before 3.6.2 (TRIP has no such key).
    assert "ended_at_home" not in TRIP
    for value in (True, False, None):
        assert _errors(_trip(ended_at_home=value)) == [], value


def _trip(**changes: object) -> dict:
    message = copy.deepcopy(TRIP_END)
    message["trip"].update(changes)
    return message


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("a trip on a live message", {**LIVE, "trip": TRIP}),
        ("trip_end without a trip", {k: v for k, v in TRIP_END.items() if k != "trip"}),
        (
            "trip_resend without a trip",
            {k: v for k, v in TRIP_RESEND.items() if k != "trip"},
        ),
        ("a trip on a test message", {**TEST, "trip": TRIP}),
        ("a missing key", {k: v for k, v in LIVE.items() if k != "obd_at"}),
        ("schema 2", {**LIVE, "schema": 2}),
        ("a null extended reading", {**LIVE, "extended": {"oil_temp_c": None}}),
        ("a custom key not cp<id>", {**LIVE, "custom": {"oil": LIVE["custom"]["cp3"]}}),
        ("both consumptions", _trip(avg_consumption_kwh_100km=1.0)),
        ("sent_at not a time", {**LIVE, "sent_at": "yesterday"}),
        ("rpm as text", {**LIVE, "rpm": "2100"}),
        ("ended_at_home as text", _trip(ended_at_home="yes")),
    ],
)
def test_what_the_app_never_sends_is_rejected(name: str, message: dict) -> None:
    assert _errors(message), name
