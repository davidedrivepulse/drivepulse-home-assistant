"""Receives the DrivePulse webhook messages and keeps the vehicle state."""

from __future__ import annotations

import logging
import math
import re
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
    CONF_SOURCES,
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
    MSG_TRIP_RECOVERED,
    MSG_TRIP_RESEND,
    MSG_TRIP_START,
)
from .units import SOURCE_UNITS, convert

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

# `extended` key -> sensor key. The app puts only the readings the car gave
# in `extended`, so a key missing from it is a null. hv_soc_pct, odometer_km,
# fuel_level_l and range_km are left out: they are the same numbers as the
# top-level keys above.
EXTENDED_KEYS: dict[str, str] = {
    "engine_load_pct": "engine_load",
    "intake_temp_c": "intake_temperature",
    "ambient_temp_c": "outside_temperature",
    "oil_temp_c": "oil_temperature",
    "pedal_pct": "accelerator_pedal",
    "map_kpa": "intake_pressure",
    "maf_gs": "mass_air_flow",
    "fuel_rate_lh": "fuel_rate",
    "timing_advance_deg": "timing_advance",
    "short_fuel_trim_pct": "short_fuel_trim",
    "long_fuel_trim_pct": "long_fuel_trim",
    "baro_kpa": "barometric_pressure",
    "engine_run_time_s": "engine_run_time",
    "fuel_rail_kpa": "fuel_rail_pressure",
    "distance_with_mil_km": "distance_with_mil",
    "distance_since_clear_km": "distance_since_codes_cleared",
    "torque_nm": "torque",
    "power_kw": "power",
    "catalyst_temp_c": "catalyst_temperature",
    "egt_c": "exhaust_temperature",
    "dpf_temp_c": "dpf_temperature",
    "dpf_delta_kpa": "dpf_pressure_difference",
    "dpf_soot_calc_g": "dpf_soot_calculated",
    "dpf_soot_meas_g": "dpf_soot_measured",
    "dpf_load_pct": "dpf_load",
    "dpf_km_since_regen": "distance_since_dpf_regeneration",
    "adblue_level_pct": "adblue_level",
    "gearbox_temp_c": "gearbox_temperature",
    "hv_soh_pct": "hv_battery_health",
    "hv_battery_temp_c": "hv_battery_temperature",
}
# `extended` yes/no readings -> binary sensor key.
EXTENDED_FLAGS: dict[str, str] = {"dpf_regen_active": "dpf_regenerating"}

# A missing value in a message makes the sensor "unavailable", EXCEPT for
# these: the app only sends them in some messages (the odometer and the codes
# come with trip_end, not with every live), so a null must not blank them.
# The extended ones change slowly and are missing whenever the adapter is not
# connected (a trip_end after the engine is off).
STICKY_KEYS = {
    "odometer",
    "range",
    "trouble_codes",
    "hv_battery_health",
    "adblue_level",
    "distance_with_mil",
    "distance_since_codes_cleared",
    "distance_since_dpf_regeneration",
}

# Custom PIDs: the user's own requests to the car, configured in the app, sent
# under `custom` with a stable key `cp<id>` (a rename keeps the key). More than
# this many per vehicle is not a car, it is a broken or forged sender.
CUSTOM_ID = re.compile(r"cp[0-9]{1,6}")
MAX_CUSTOM = 50

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
# Read by Parked at home (_at_home), never kept in the last trip summary.
TRIP_AT_HOME = "ended_at_home"


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
class CustomPid:
    """One custom PID of a vehicle: what the user called it, and its reading."""

    name: str
    unit: str | None
    value: float | int | None = None
    at: str | None = None

    def as_event(self) -> dict[str, Any]:
        return {"name": self.name, "value": self.value, "unit": self.unit}


def _custom_from_dict(data: Any) -> dict[str, CustomPid]:
    if not isinstance(data, dict):
        return {}
    return {
        cp_id: CustomPid(
            name=_text(item.get("name")) or cp_id, unit=_text(item.get("unit"), 16)
        )
        for cp_id, item in list(data.items())[:MAX_CUSTOM]
        if isinstance(cp_id, str) and CUSTOM_ID.fullmatch(cp_id) and isinstance(item, dict)
    }


@dataclass
class Vehicle:
    """What the integration knows about one vehicle (named in the app)."""

    name: str
    slug: str
    keys: set[str] = field(default_factory=set)
    values: dict[str, float | int | None] = field(default_factory=dict)
    flags: dict[str, bool | None] = field(default_factory=dict)
    custom: dict[str, CustomPid] = field(default_factory=dict)
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
            # Name and unit only: the entities come back after a restart, the
            # reading comes with the next message.
            "custom": {
                cp_id: {"name": pid.name, "unit": pid.unit}
                for cp_id, pid in self.custom.items()
            },
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
            custom=_custom_from_dict(data.get("custom")),
            in_trip=bool(data.get("in_trip", False)),
            last_trip=data.get("last_trip"),
            at_home=(
                data["at_home"] if isinstance(data.get("at_home"), bool) else None
            ),
            at_home_known=bool(data.get("at_home_known", False)),
        )


def _sources(options: Any) -> dict[str, dict[str, str]]:
    """The custom PIDs standing in for built-in sensors, as saved in the options."""
    found: dict[str, dict[str, str]] = {}
    for slug, mapping in (options if isinstance(options, dict) else {}).items():
        if not isinstance(slug, str) or not isinstance(mapping, dict):
            continue
        found[slug] = {
            key: cp_id
            for key, cp_id in mapping.items()
            if key in SOURCE_UNITS
            and isinstance(cp_id, str)
            and CUSTOM_ID.fullmatch(cp_id)
        }
    return found


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
        # Read once: a change of the options reloads the entry.
        self.sources = _sources(entry.options.get(CONF_SOURCES))
        self._store: Store[dict[str, Any]] = Store(
            hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._new_vehicle_listeners: list[Callable[[Vehicle], None]] = []
        self._new_key_listeners: list[Callable[[Vehicle, str], None]] = []
        self._new_custom_listeners: list[Callable[[Vehicle, str], None]] = []
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
    def listen_new_custom(self, listener: Callable[[Vehicle, str], None]) -> None:
        """Called with (vehicle, cp_id) when a custom PID first has a number."""
        self._new_custom_listeners.append(listener)

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
        if event == MSG_TRIP_RECOVERED:
            return self._recovered(payload)

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
    def _new_key(self, vehicle: Vehicle, key: str) -> None:
        if key not in vehicle.keys:
            vehicle.keys.add(key)
            for listener in self._new_key_listeners:
                listener(vehicle, key)

    @callback
    def _set_number(self, vehicle: Vehicle, key: str, value: Any) -> None:
        number = _number(value)
        if number is None:
            if key not in STICKY_KEYS:
                vehicle.values[key] = None
            return
        vehicle.values[key] = number
        self._new_key(vehicle, key)

    @callback
    def _apply_extended(self, vehicle: Vehicle, extended: dict[str, Any]) -> None:
        """The extended readings: a key missing here is a null."""
        for webhook_key, key in EXTENDED_KEYS.items():
            self._set_number(vehicle, key, extended.get(webhook_key))
        for webhook_key, key in EXTENDED_FLAGS.items():
            flag = extended.get(webhook_key)
            vehicle.flags[key] = flag if isinstance(flag, bool) else None
            if isinstance(flag, bool):
                self._new_key(vehicle, key)

    @callback
    def _apply_custom(self, vehicle: Vehicle, custom: dict[str, Any]) -> None:
        """The custom PIDs: a PID missing here has no reading now.

        A PID becomes a sensor with its first number, so one the car never
        answers does not show up. Its name and unit follow the app: a rename
        or a new unit in the app changes the same sensor.
        """
        seen: set[str] = set()
        for cp_id, item in custom.items():
            if not (
                isinstance(cp_id, str)
                and CUSTOM_ID.fullmatch(cp_id)
                and isinstance(item, dict)
            ):
                continue
            number = _number(item.get("value"))
            pid = vehicle.custom.get(cp_id)
            new = pid is None
            if pid is None:
                if number is None or len(vehicle.custom) >= MAX_CUSTOM:
                    continue
                pid = vehicle.custom[cp_id] = CustomPid(name=cp_id, unit=None)
            pid.name = _text(item.get("name")) or pid.name
            pid.unit = _text(item.get("unit"), 16)
            pid.value = number
            pid.at = _text(item.get("at"), 40) if number is not None else None
            seen.add(cp_id)
            if new:
                for listener in self._new_custom_listeners:
                    listener(vehicle, cp_id)
        for cp_id, pid in vehicle.custom.items():
            if cp_id not in seen:
                pid.value = pid.at = None

    @callback
    def source_of(self, vehicle: Vehicle, key: str) -> str | None:
        """The custom PID a built-in sensor takes its value from, if any."""
        return self.sources.get(vehicle.slug, {}).get(key)

    @callback
    def _apply_sources(self, vehicle: Vehicle) -> None:
        """Built-in sensors that read a custom PID instead of the app's number.

        In the built-in sensor's unit when Home Assistant can convert, as is
        otherwise. A PID without a reading now is a null, with the usual rule
        for the sticky sensors.
        """
        for key, cp_id in self.sources.get(vehicle.slug, {}).items():
            pid = vehicle.custom.get(cp_id)
            value = None
            if pid is not None and pid.value is not None:
                value = convert(pid.value, pid.unit, SOURCE_UNITS[key])
            self._set_number(vehicle, key, value)

    @callback
    def _apply(self, vehicle: Vehicle, event: str, payload: dict[str, Any]) -> None:
        sources = self.sources.get(vehicle.slug, {})
        for webhook_key, key in NUMERIC_KEYS.items():
            if key in sources:
                continue  # read from its custom PID below
            if webhook_key in payload:  # missing: an older app, no change
                self._set_number(vehicle, key, payload[webhook_key])
        if isinstance(payload.get("extended"), dict):
            self._apply_extended(vehicle, payload["extended"])
        if isinstance(payload.get("custom"), dict):  # app 3.5.9 and later
            self._apply_custom(vehicle, payload["custom"])
            self._apply_sources(vehicle)

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
        at trip_end, and with a trip_resend or a trip_recovered that becomes
        the last trip.

        True or False sets it, and the first one creates the entity. None
        (switch off in the app, no Home place for this car, GPS lost before
        the car stopped) makes it unknown. No key at all (an app from before
        the switch) leaves it as it was. trip_start, live and test never come
        here: a trip that starts and is then thrown away by the app sends no
        trip_end, so turning the sensor off at trip_start would leave it off
        with the car in the garage.
        """
        if TRIP_AT_HOME not in trip:
            return
        value = trip[TRIP_AT_HOME]
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
    def _recovered(self, payload: dict[str, Any]) -> web.Response | None:
        """A real trip left open when the phone stopped the app, closed later.

        The app closed it with its real end time when it opened again, maybe
        hours later. One rule: everything happens only if it becomes the last
        trip, with the rule of a resend (the same trip or a more recent one).
        Then it ends the trip in progress, becomes the last trip and brings
        Parked at home. An older one changes nothing: a more recent trip
        already ended the trip in progress back then, and a trip in progress
        now is another one. Not through _apply (every reading at the top is
        null) and no event on the bus: a drivepulse_trip_end now would run
        "the car arrived" automations at the wrong hour.
        """
        trip = payload.get("trip")
        if not isinstance(trip, dict):
            return web.Response(status=400, text="trip_recovered without a trip")
        vehicle = self._vehicle_for(payload)
        if vehicle is None:
            return web.Response(status=400, text="too many vehicles")
        summary = _trip_summary(trip)
        if not _more_recent(summary, vehicle.last_trip):
            return None
        vehicle.in_trip = False
        vehicle.last_trip = summary
        self._at_home(vehicle, trip)
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
        sources = self.sources.get(vehicle.slug, {})
        for key in EVENT_FIELDS:
            if NUMERIC_KEYS.get(key) in sources:
                # The value the sensor shows, from its custom PID.
                data[key] = vehicle.values.get(NUMERIC_KEYS[key])
                continue
            data[key] = payload[key] if _plain(payload.get(key)) else None
        # The custom PIDs by their stable key, with the name and unit the user
        # gave them; value None when the car did not answer this time.
        data["custom"] = {
            cp_id: pid.as_event() for cp_id, pid in vehicle.custom.items()
        }
        if event == MSG_TRIP_END and vehicle.last_trip:
            data["trip"] = dict(vehicle.last_trip)
        self.hass.bus.async_fire(
            EVENT_TRIP_START if event == MSG_TRIP_START else EVENT_TRIP_END, data
        )
