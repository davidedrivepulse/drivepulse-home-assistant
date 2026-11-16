"""Sensors of a DrivePulse vehicle."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DrivePulseConfigEntry
from .entity import DrivePulseEntity
from .hub import CustomPid, DrivePulseHub, Vehicle
from .units import custom_unit

LAST_TRIP = "last_trip_distance"


def _extended(
    key: str,
    unit: str | None,
    device_class: SensorDeviceClass | None = None,
    *,
    enabled: bool = True,
    precision: int | None = None,
) -> SensorEntityDescription:
    """A reading of `extended`. The ones that change every second (engine
    load, pedal, air flow, ...) are disabled by default, like speed and rpm."""
    return SensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=device_class,
        native_unit_of_measurement=unit,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=enabled,
        suggested_display_precision=precision,
    )


_T = SensorDeviceClass.TEMPERATURE
_P = SensorDeviceClass.PRESSURE
_D = SensorDeviceClass.DISTANCE
_C = UnitOfTemperature.CELSIUS
_KPA = UnitOfPressure.KPA
_KM = UnitOfLength.KILOMETERS

EXTENDED_DESCRIPTIONS = (
    _extended("engine_load", PERCENTAGE, enabled=False),
    _extended("intake_temperature", _C, _T),
    _extended("outside_temperature", _C, _T),
    _extended("oil_temperature", _C, _T),
    _extended("accelerator_pedal", PERCENTAGE, enabled=False),
    _extended("intake_pressure", _KPA, _P, enabled=False),
    _extended("mass_air_flow", "g/s", enabled=False),
    # No volume flow device class: litres per hour needs a newer Home Assistant.
    _extended("fuel_rate", "L/h", enabled=False, precision=2),
    _extended("timing_advance", DEGREE, enabled=False),
    _extended("short_fuel_trim", PERCENTAGE, enabled=False),
    _extended("long_fuel_trim", PERCENTAGE, enabled=False),
    _extended("barometric_pressure", _KPA, _P),
    _extended(
        "engine_run_time", UnitOfTime.SECONDS, SensorDeviceClass.DURATION, enabled=False
    ),
    _extended("fuel_rail_pressure", _KPA, _P, enabled=False),
    _extended("distance_with_mil", _KM, _D),
    _extended("distance_since_codes_cleared", _KM, _D),
    _extended("torque", "N·m", enabled=False),
    _extended("power", UnitOfPower.KILO_WATT, SensorDeviceClass.POWER, enabled=False),
    _extended("catalyst_temperature", _C, _T),
    _extended("exhaust_temperature", _C, _T),
    _extended("dpf_temperature", _C, _T),
    _extended("dpf_pressure_difference", _KPA, _P, precision=2),
    _extended("dpf_soot_calculated", UnitOfMass.GRAMS, SensorDeviceClass.WEIGHT),
    _extended("dpf_soot_measured", UnitOfMass.GRAMS, SensorDeviceClass.WEIGHT),
    _extended("dpf_load", PERCENTAGE, precision=1),
    _extended("distance_since_dpf_regeneration", _KM, _D, precision=1),
    _extended("adblue_level", PERCENTAGE, precision=1),
    _extended("gearbox_temperature", _C, _T, precision=1),
    _extended("hv_battery_health", PERCENTAGE, precision=1),
    _extended("hv_battery_temperature", _C, _T, precision=1),
)


DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    d.key: d
    for d in (
        SensorEntityDescription(
            key="fuel_level",
            translation_key="fuel_level",
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="battery_level",
            translation_key="battery_level",
            device_class=SensorDeviceClass.BATTERY,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="range",
            translation_key="range",
            device_class=SensorDeviceClass.DISTANCE,
            native_unit_of_measurement=UnitOfLength.KILOMETERS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="odometer",
            translation_key="odometer",
            device_class=SensorDeviceClass.DISTANCE,
            native_unit_of_measurement=UnitOfLength.KILOMETERS,
            state_class=SensorStateClass.TOTAL_INCREASING,
            suggested_display_precision=1,
        ),
        SensorEntityDescription(
            key="battery_voltage",
            translation_key="battery_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
        ),
        SensorEntityDescription(
            key="coolant_temperature",
            translation_key="coolant_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="trouble_codes",
            translation_key="trouble_codes",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="fuel_volume",
            translation_key="fuel_volume",
            native_unit_of_measurement=UnitOfVolume.LITERS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="speed",
            translation_key="speed",
            device_class=SensorDeviceClass.SPEED,
            native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="engine_speed",
            translation_key="engine_speed",
            native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        *EXTENDED_DESCRIPTIONS,
    )
}

LAST_TRIP_DESCRIPTION = SensorEntityDescription(
    key=LAST_TRIP,
    translation_key=LAST_TRIP,
    device_class=SensorDeviceClass.DISTANCE,
    native_unit_of_measurement=UnitOfLength.KILOMETERS,
    suggested_display_precision=1,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DrivePulseConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the sensors of the known vehicles, and of the ones to come."""
    hub = entry.runtime_data

    def vehicle_entities(vehicle: Vehicle) -> list[DrivePulseSensor]:
        found: list[DrivePulseSensor] = [DrivePulseLastTrip(hub, vehicle)]
        found += [
            DrivePulseSensor(hub, vehicle, DESCRIPTIONS[key])
            for key in sorted(vehicle.keys)
            if key in DESCRIPTIONS
        ]
        return found

    async_add_entities(
        entity
        for vehicle in hub.vehicles.values()
        for entity in vehicle_entities(vehicle)
    )
    hub.listen_new_vehicle(
        lambda vehicle: async_add_entities(vehicle_entities(vehicle))
    )

    def optional_sensor(vehicle: Vehicle, key: str) -> None:
        """A sensor that appears when the car first sends its number."""
        if key in DESCRIPTIONS:
            async_add_entities([DrivePulseSensor(hub, vehicle, DESCRIPTIONS[key])])

    hub.listen_new_key(optional_sensor)

    # Custom PIDs: the ones known before a restart now, the new ones live.
    async_add_entities(
        DrivePulseCustomSensor(hub, vehicle, cp_id)
        for vehicle in hub.vehicles.values()
        for cp_id in vehicle.custom
    )
    hub.listen_new_custom(
        lambda vehicle, cp_id: async_add_entities(
            [DrivePulseCustomSensor(hub, vehicle, cp_id)]
        )
    )


class DrivePulseSensor(DrivePulseEntity, SensorEntity):
    """A number read from the car."""

    def __init__(
        self,
        hub: DrivePulseHub,
        vehicle: Vehicle,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(hub, vehicle, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | None:
        return self._vehicle.values.get(self._key)

    @property
    def available(self) -> bool:
        """'Unavailable' while the car has not given this value."""
        return self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._key == "trouble_codes" and self._vehicle.codes is not None:
            return {"codes": list(self._vehicle.codes)}
        if source := self._hub.source_of(self._vehicle, self._key):
            return {"source_pid": source}
        return None


class DrivePulseLastTrip(DrivePulseSensor):
    """Distance of the last finished trip, with its summary as attributes."""

    def __init__(self, hub: DrivePulseHub, vehicle: Vehicle) -> None:
        super().__init__(hub, vehicle, LAST_TRIP_DESCRIPTION)

    @property
    def native_value(self) -> float | int | None:
        trip = self._vehicle.last_trip
        value = trip.get("distance_km") if trip else None
        return value if isinstance(value, (int, float)) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        trip = self._vehicle.last_trip
        return {k: v for k, v in trip.items() if k != "distance_km"} if trip else None


class DrivePulseCustomSensor(DrivePulseEntity, SensorEntity):
    """A custom PID set up in the app.

    The unique id is the PID's stable key, so a rename in the app keeps the
    entity and its history. Name and unit are the app's, read at every state
    write: they follow the app without a restart. A name given in Home
    Assistant still wins over the app's.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hub: DrivePulseHub, vehicle: Vehicle, cp_id: str) -> None:
        super().__init__(hub, vehicle, f"custom_{cp_id}")
        self._cp_id = cp_id
        self._attr_translation_key = None

    @property
    def _pid(self) -> CustomPid | None:
        return self._vehicle.custom.get(self._cp_id)

    @property
    def name(self) -> str | None:
        pid = self._pid
        return pid.name if pid else self._cp_id

    @property
    def native_value(self) -> float | int | None:
        pid = self._pid
        return pid.value if pid else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        pid = self._pid
        return custom_unit(pid.unit)[1] if pid else None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        pid = self._pid
        return custom_unit(pid.unit)[0] if pid else None

    @property
    def available(self) -> bool:
        return self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pid = self._pid
        return {"pid": self._cp_id, "measured_at": pid.at if pid else None}
