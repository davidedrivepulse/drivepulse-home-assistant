"""Receives the DrivePulse webhook messages and keeps the vehicle state."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from aiohttp import web
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    DEFAULT_VEHICLE_NAME,
    DOMAIN,
    EVENT_TRIP_END,
    EVENT_TRIP_RESENT,
    EVENT_TRIP_START,
    KNOWN_MESSAGES,
    MAX_VEHICLES,
    MSG_TEST,
    MSG_TRIP_DISCARDED,
    MSG_TRIP_END,
    MSG_TRIP_RESEND,
    MSG_TRIP_START,
)

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1

# Webhook key -> sensor key. The webhook keys are the fixed schema 1 names.
NUMERIC_KEYS: dict[str, str] = {
    "fuel_level_pct": "fuel_level",
    "hv_soc_pct": "battery_level",
    "range_km": "range",
    "odometer_km": "odometer",
    "battery_voltage": "battery_voltage",
    "coolant_temp_c": "coolant_temperature",
    "dtc_count": "trouble_codes",
    "fuel_level_l": "fuel_volume",
    "speed_kmh": "speed",
    "rpm": "engine_speed",
}

# A missing value in a message makes the sensor "unavailable", EXCEPT for
# these: the app only sends them in some messages (the odometer and the codes
# come with trip_end, not with every live), so a null must not blank them.
STICKY_KEYS = {"odometer", "range", "trouble_codes"}

# Sensors every vehicle gets on its first message. The others (fuel or
# electric charge, range, litres, speed, rpm) appear when the car first sends
# a real number for them, so a petrol car never shows an empty "battery level".
CORE_KEYS = {"battery_voltage", "coolant_temperature", "odometer", "trouble_codes"}

# What goes on the bus with the trip events. Nothing else is forwarded: no
# position, no VIN, no free text.
EVENT_FIELDS = (
    "sent_at",
    "fuel_level_pct",
    "hv_soc_pct",
    "range_km",
    "odometer_km",
    "battery_voltage",
    "dtc_count",
    "coolant_temp_c",
)
TRIP_FIELDS = (
    "start",
    "end",
    "distance_km",
    "duration_min",
    "avg_speed_kmh",
    "max_speed_kmh",
    "avg_consumption_l_100km",
    "avg_consumption_kwh_100km",
    "odometer_km",
)


def _number(value: Any) -> float | int | None:
    """A JSON number, or None. Booleans, strings, NaN and infinity are not."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _text(value: Any, limit: int = 64) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:limit] if value else None


def _plain(value: Any) -> bool:
    """A number or a short string: the only shapes forwarded from a payload."""
    return _number(value) is not None or isinstance(value, str)


def _trip_summary(trip: dict[str, Any]) -> dict[str, Any]:
    """The trip fields kept and forwarded: no id, no route, nothing unknown."""
    return {key: trip[key] for key in TRIP_FIELDS if key in trip and _plain(trip[key])}


def _trip_time(trip: dict[str, Any] | None) -> datetime | None:
    """When a trip ended, or started if it has no end; None if neither parses."""
    for key in ("end", "start"):
        value = (trip or {}).get(key)
        when = dt_util.parse_datetime(value) if isinstance(value, str) else None
        if when is not None:
            return when if when.tzinfo else when.replace(tzinfo=dt_util.UTC)
    return None


def _name_and_slug(payload: dict[str, Any]) -> tuple[str, str]:
    """The vehicle's name in a message, and the slug it is stored under."""
    name = _text(payload.get("vehicle")) or DEFAULT_VEHICLE_NAME
    return name, slugify(name) or slugify(DEFAULT_VEHICLE_NAME)


def _more_recent(trip: dict[str, Any], last: dict[str, Any] | None) -> bool:
    """Whether a resent trip should become the last trip.

    The same trip counts too (>=): sent again after a correction in the app,
    it brings the corrected values. An older trip never does.
    """
    if not last:
        return True
    new = _trip_time(trip)
    if new is None:
        return False
    old = _trip_time(last)
    return old is None or new >= old


@dataclass
class Vehicle:
    """What the integration knows about one vehicle (named in the app)."""

    name: str
    slug: str
    keys: set[str] = field(default_factory=set)
    values: dict[str, float | int | None] = field(default_factory=dict)
    codes: list[str] | None = None
    in_trip: bool = False
    adapter_connected: bool | None = None
    last_trip: dict[str, Any] | None = None
    # Where the last trip ended: in a Home place of this car (True), not
    # (False), or unknown (None). A yes/no worked out on the phone, never a
    # position. at_home_known turns True with the first yes or no and never
    # back: the entity exists from then on.
    at_home: bool | None = None
    at_home_known: bool = False

    def as_dict(self) -> dict[str, Any]:
        """The part worth keeping across a restart: the sticky values only."""
        return {
            "name": self.name,
            "keys": sorted(self.keys),
            "values": {k: v for k, v in self.values.items() if k in STICKY_KEYS},
            "codes": self.codes,
            "in_trip": self.in_trip,
            "last_trip": self.last_trip,
            "at_home": self.at_home,
            "at_home_known": self.at_home_known,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Vehicle:
        name = data.get("name") or DEFAULT_VEHICLE_NAME
        return cls(
            name=name,
            slug=slugify(name) or slugify(DEFAULT_VEHICLE_NAME),
            keys=set(data.get("keys", [])),
            values=dict(data.get("values", {})),
            codes=data.get("codes"),
            in_trip=bool(data.get("in_trip", False)),
            last_trip=data.get("last_trip"),
            at_home=(
                data["at_home"] if isinstance(data.get("at_home"), bool) else None
            ),
            at_home_known=bool(data.get("at_home_known", False)),
        )


def signal(entry_id: str, slug: str) -> str:
    """Dispatcher signal an entity listens to for one vehicle."""
    return f"{DOMAIN}_{entry_id}_{slug}"


def device_identifier(entry_id: str, slug: str) -> tuple[str, str]:
    """The device identifier: entry + vehicle name, never a VIN."""
    return (DOMAIN, f"{entry_id}_{slug}")


class DrivePulseHub:
    """One config entry: the webhook handler and the vehicles it has seen."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.vehicles: dict[str, Vehicle] = {}
        self._store: Store[dict[str, Any]] = Store(
            hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._new_vehicle_listeners: list[Callable[[Vehicle], None]] = []
        self._new_key_listeners: list[Callable[[Vehicle, str], None]] = []
        self._at_home_listeners: list[Callable[[Vehicle], None]] = []

    async def async_load(self) -> None:
        data = await self._store.async_load()
        for item in (data or {}).get("vehicles", []):
            vehicle = Vehicle.from_dict(item)
            self.vehicles[vehicle.slug] = vehicle

    @callback
    def _async_save(self) -> None:
        self._store.async_delay_save(
            lambda: {"vehicles": [v.as_dict() for v in self.vehicles.values()]}, 2
        )

    async def async_flush(self) -> None:
        """Write what is waiting to be saved (called on unload)."""
        await self._store.async_save(
            {"vehicles": [v.as_dict() for v in self.vehicles.values()]}
        )

    async def async_remove_storage(self) -> None:
        await self._store.async_remove()

    def slug_of_device(self, identifiers: set[tuple[str, str]]) -> str | None:
        """The vehicle slug behind a device's identifiers, or None if not ours."""
        prefix = f"{self.entry.entry_id}_"
        for domain, value in identifiers:
            if domain == DOMAIN and value.startswith(prefix):
                return value[len(prefix) :]
        return None

    async def async_forget_vehicle(self, slug: str) -> bool:
        """Drop one vehicle and save at once; False while it is in a trip.

        Called when the user deletes the vehicle's device. The vehicle must
        leave the store too, or it would be back on the next start and keep
        counting against the vehicle limit. A vehicle in the middle of a trip
        is kept: its trip_end is on the way and would recreate it anyway.
        """
        vehicle = self.vehicles.get(slug)
        if vehicle is None:
            return True  # already forgotten: nothing to do
        if vehicle.in_trip:
            return False
        del self.vehicles[slug]
        await self.async_flush()
        return True

    # -- platforms register here to create entities as vehicles/keys appear --

    @callback
    def listen_new_vehicle(self, listener: Callable[[Vehicle], None]) -> None:
        self._new_vehicle_listeners.append(listener)

    @callback
    def listen_new_key(self, listener: Callable[[Vehicle, str], None]) -> None:
        self._new_key_listeners.append(listener)

    @callback
    def listen_at_home_known(self, listener: Callable[[Vehicle], None]) -> None:
        self._at_home_listeners.append(listener)

    # -- the webhook --------------------------------------------------------

    async def handle_webhook(
        self, hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response | None:
        """Handle one POST from the app."""
        try:
            payload = await request.json()
        except ValueError:
            _LOGGER.debug("Webhook body is not JSON")
            return web.Response(status=400, text="invalid JSON")
        if not isinstance(payload, dict):
            return web.Response(status=400, text="expected a JSON object")

        event = payload.get("event")
        if event not in KNOWN_MESSAGES:
            # A newer app may send events this version does not know: accept
            # and ignore, so the app does not report a failure.
            _LOGGER.debug("Ignoring unknown DrivePulse event %r", event)
            return None
        if event == MSG_TEST:
            return self._test(payload)
        if event == MSG_TRIP_RESEND:
            return self._resend(payload)
        if event == MSG_TRIP_DISCARDED:
            return self._discarded(payload)

        vehicle = self._vehicle_for(payload)
        if vehicle is None:
            return web.Response(status=400, text="too many vehicles")
        self._apply(vehicle, event, payload)
        return None

    def _vehicle_for(self, payload: dict[str, Any]) -> Vehicle | None:
        name, slug = _name_and_slug(payload)
        vehicle = self.vehicles.get(slug)
        if vehicle is not None:
            return vehicle
        if len(self.vehicles) >= MAX_VEHICLES:
            _LOGGER.warning(
                "DrivePulse: ignoring a new vehicle, limit of %s", MAX_VEHICLES
            )
            return None
        vehicle = Vehicle(name=name, slug=slug, keys=set(CORE_KEYS))
        self.vehicles[slug] = vehicle
        self.ensure_device(vehicle)
        for listener in self._new_vehicle_listeners:
            listener(vehicle)
        return vehicle

    @callback
    def ensure_device(self, vehicle: Vehicle) -> None:
        """Create the vehicle's device (one per vehicle name, no VIN)."""
        dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.entry.entry_id,
            identifiers={device_identifier(self.entry.entry_id, vehicle.slug)},
            name=vehicle.name,
            manufacturer="DrivePulse",
            model="Vehicle (OBD2)",
        )

    @callback
    def _apply(self, vehicle: Vehicle, event: str, payload: dict[str, Any]) -> None:
        for webhook_key, key in NUMERIC_KEYS.items():
            if webhook_key not in payload:
                continue  # an older app: no change
            number = _number(payload[webhook_key])
            if number is None:
                if key not in STICKY_KEYS:
                    vehicle.values[key] = None
                continue
            vehicle.values[key] = number
            if key not in vehicle.keys:
                vehicle.keys.add(key)
                for listener in self._new_key_listeners:
                    listener(vehicle, key)

        if isinstance(payload.get("dtc"), list):
            vehicle.codes = [
                code.strip()[:12]
                for code in payload["dtc"][:50]
                if isinstance(code, str) and code.strip()
            ]

        if isinstance(payload.get("obd_connected"), bool):
            vehicle.adapter_connected = payload["obd_connected"]

        if event == MSG_TRIP_START:
            vehicle.in_trip = True
        elif event == MSG_TRIP_END:
            vehicle.in_trip = False
            trip = payload.get("trip")
            if isinstance(trip, dict):
                vehicle.last_trip = _trip_summary(trip)
                self._at_home(vehicle, trip)
        if event in (MSG_TRIP_START, MSG_TRIP_END):
            self._fire_trip_event(vehicle, event, payload)

        self._async_save()
        async_dispatcher_send(self.hass, signal(self.entry.entry_id, vehicle.slug))

    @callback
    def _at_home(self, vehicle: Vehicle, trip: dict[str, Any]) -> None:
        """Where the last trip ended, as the phone worked it out.

        It belongs to the last trip, so it changes when the last trip does:
        at trip_end, and with a trip_resend that becomes the last trip.

        True or False sets it, and the first one creates the entity. None
        (switch off in the app, no Home place for this car, GPS lost before
        the car stopped) makes it unknown. No key at all (an app from before
        the switch) leaves it as it was. trip_start, live and test never come
        here: a trip that starts and is then thrown away by the app sends no
        trip_end, so turning the sensor off at trip_start would leave it off
        with the car in the garage.
        """
        if "ended_at_home" not in trip:
            return
        value = trip["ended_at_home"]
        if not isinstance(value, bool):
            vehicle.at_home = None
            return
        vehicle.at_home = value
        if not vehicle.at_home_known:
            vehicle.at_home_known = True
            for listener in self._at_home_listeners:
                listener(vehicle)

    @callback
    def _test(self, payload: dict[str, Any]) -> web.Response | None:
        """The app's "Test send" button.

        The vehicle's device and its entities appear (without values), so the
        user sees the integration work before the first trip. Nothing else:
        a test is not a reading of the car, so no value, no adapter flag, no
        trip in progress, no last trip and no event on the bus.
        """
        known = len(self.vehicles)
        if self._vehicle_for(payload) is None:
            return web.Response(status=400, text="too many vehicles")
        if len(self.vehicles) != known:
            self._async_save()
        return None

    @callback
    def _discarded(self, payload: dict[str, Any]) -> web.Response | None:
        """The trip that had just started was a false start: the app dropped it.

        Its trip_start already turned Trip in progress on, and no trip_end
        will come. Only that goes back off: no value, no adapter flag, no last
        trip, no Parked at home and no event on the bus (an automation can
        follow Trip in progress). A vehicle this Home Assistant does not know
        is not created for a trip that does not exist.
        """
        vehicle = self.vehicles.get(_name_and_slug(payload)[1])
        if vehicle is None or not vehicle.in_trip:
            return None
        vehicle.in_trip = False
        self._async_save()
        async_dispatcher_send(self.hass, signal(self.entry.entry_id, vehicle.slug))
        return None

    @callback
    def _resend(self, payload: dict[str, Any]) -> web.Response | None:
        """A saved trip the user sent again from the app.

        Not through _apply: every reading at the top of this message is null,
        so it would blank the sensors and turn "adapter connected" off, and it
        must not end a trip in progress either. Only the last trip can change,
        and only to the same trip or a more recent one; Parked at home changes
        with it, since it belongs to the last trip (Home Assistant was off at
        the real end). The bus gets drivepulse_trip_resent, never
        drivepulse_trip_end.
        """
        trip = payload.get("trip")
        if not isinstance(trip, dict):
            return web.Response(status=400, text="trip_resend without a trip")
        vehicle = self._vehicle_for(payload)
        if vehicle is None:
            return web.Response(status=400, text="too many vehicles")
        summary = _trip_summary(trip)
        if _more_recent(summary, vehicle.last_trip):
            vehicle.last_trip = summary
            self._at_home(vehicle, trip)
            self._async_save()
            async_dispatcher_send(self.hass, signal(self.entry.entry_id, vehicle.slug))
        sent_at = payload.get("sent_at")
        self.hass.bus.async_fire(
            EVENT_TRIP_RESENT,
            {
                "device_id": self._device_id(vehicle),
                "vehicle": vehicle.name,
                "sent_at": sent_at if _plain(sent_at) else None,
                "trip": summary,
            },
        )
        return None

    def _device_id(self, vehicle: Vehicle) -> str | None:
        # Not `async_get_device(identifiers=...)`: it is deprecated (identifiers
        # are no longer unique across config entries) and raises on recent Home
        # Assistant. Our devices are the ones of this entry, so look there.
        identifier = device_identifier(self.entry.entry_id, vehicle.slug)
        device = next(
            (
                found
                for found in dr.async_entries_for_config_entry(
                    dr.async_get(self.hass), self.entry.entry_id
                )
                if identifier in found.identifiers
            ),
            None,
        )
        return device.id if device else None

    def _fire_trip_event(
        self, vehicle: Vehicle, event: str, payload: dict[str, Any]
    ) -> None:
        data: dict[str, Any] = {
            "device_id": self._device_id(vehicle),
            "vehicle": vehicle.name,
        }
        # Every field is always there (None when the car did not give it), so
        # an automation template never trips on a missing key.
        for key in EVENT_FIELDS:
            data[key] = payload[key] if _plain(payload.get(key)) else None
        if event == MSG_TRIP_END and vehicle.last_trip:
            data["trip"] = dict(vehicle.last_trip)
        self.hass.bus.async_fire(
            EVENT_TRIP_START if event == MSG_TRIP_START else EVENT_TRIP_END, data
        )
