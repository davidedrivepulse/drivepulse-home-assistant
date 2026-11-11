"""Parked at home: where the last trip ended, as a yes or no from the phone.

The app sends trip.ended_at_home (true, false or null) with trip_end and
trip_resend, with its switch on (off by default). Never a position. It
belongs to the last trip, so a resend changes it only when it becomes the
last trip.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import find, message
from .test_trip_resend import resend, trip

KEY = "parked_at_home"


def end(at_home: Any = "missing", **fields: Any) -> dict[str, Any]:
    the_trip = trip("2026-10-12T08:00:00Z")
    if at_home != "missing":
        the_trip["ended_at_home"] = at_home
    return message("trip_end", trip=the_trip, **fields)


def at_home_state(hass: HomeAssistant, entry, vehicle: str = "my_car") -> str | None:
    entity_id = find(hass, entry, "binary_sensor", KEY, vehicle)
    if entity_id is None:
        return None
    return hass.states.get(entity_id).state


async def test_it_appears_with_the_first_yes(hass: HomeAssistant, entry, send) -> None:
    await send(end())
    await send(end(None))
    assert at_home_state(hass, entry) is None, "no yes or no yet: no entity"

    assert await send(end(True)) == 200
    assert at_home_state(hass, entry) == STATE_ON


async def test_it_appears_with_the_first_no_too(
    hass: HomeAssistant, entry, send
) -> None:
    assert await send(end(False)) == 200
    assert at_home_state(hass, entry) == STATE_OFF


async def test_null_is_unknown_and_a_missing_key_changes_nothing(
    hass: HomeAssistant, entry, send
) -> None:
    await send(end(True))
    await send(end())
    assert at_home_state(hass, entry) == STATE_ON, "an older app: left as it was"
    await send(end(None))
    assert at_home_state(hass, entry) == STATE_UNKNOWN
    await send(end(False))
    assert at_home_state(hass, entry) == STATE_OFF


async def test_trip_start_live_and_test_do_not_touch_it(
    hass: HomeAssistant, entry, send
) -> None:
    await send(end(True))
    # A trip that starts and is then thrown away by the app sends no
    # trip_end: if trip_start turned the sensor off, it would stay off with
    # the car in the garage.
    await send(message("trip_start"))
    assert at_home_state(hass, entry) == STATE_ON
    await send(message("live"))
    await send(message("test"))
    assert at_home_state(hass, entry) == STATE_ON


async def test_a_resend_that_becomes_the_last_trip_brings_its_value(
    hass: HomeAssistant, entry, send
) -> None:
    await send(end(True))
    # Home Assistant was off at the real end of a more recent trip.
    newer = trip("2026-10-13T08:00:00Z", ended_at_home=False)
    assert await send(resend(newer)) == 200
    assert at_home_state(hass, entry) == STATE_OFF
    # The same trip sent again counts too (>=), null included.
    await send(resend(trip("2026-10-13T08:00:00Z", ended_at_home=None)))
    assert at_home_state(hass, entry) == STATE_UNKNOWN


async def test_an_older_resend_does_not_touch_it(
    hass: HomeAssistant, entry, send
) -> None:
    await send(end(True))
    older = trip("2026-10-11T08:00:00Z", ended_at_home=False)
    assert await send(resend(older)) == 200
    assert at_home_state(hass, entry) == STATE_ON
    # Not even inside: the entity is redrawn only on the next update, so a
    # value changed without a signal would show up with the next live.
    assert await send(message("live")) == 200
    assert at_home_state(hass, entry) == STATE_ON


async def test_a_resend_can_create_it(hass: HomeAssistant, entry, send) -> None:
    assert await send(resend(trip("2026-10-13T08:00:00Z", ended_at_home=True))) == 200
    assert at_home_state(hass, entry) == STATE_ON


async def test_each_car_has_its_own(hass: HomeAssistant, entry, send) -> None:
    await send(end(True))
    await send(end(False, vehicle="Panda"))
    assert at_home_state(hass, entry) == STATE_ON
    assert at_home_state(hass, entry, "panda") == STATE_OFF


async def test_it_survives_a_restart(
    hass: HomeAssistant, entry, send, hass_storage
) -> None:
    await send(end(False))
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    saved = hass_storage[f"drivepulse.{entry.entry_id}"]["data"]["vehicles"]
    assert saved[0]["at_home"] is False
    assert saved[0]["at_home_known"] is True

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert at_home_state(hass, entry) == STATE_OFF


async def test_after_a_restart_unknown_stays_unknown(
    hass: HomeAssistant, entry, send
) -> None:
    await send(end(True))
    await send(end(None))
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert at_home_state(hass, entry) == STATE_UNKNOWN


async def test_never_known_no_entity_after_a_restart(
    hass: HomeAssistant, entry, send
) -> None:
    await send(end(None))
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert at_home_state(hass, entry) is None
