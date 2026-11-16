"""Units of the custom PIDs, and using a custom PID for a built-in sensor."""

from __future__ import annotations

from homeassistant.components.sensor import UNIT_CONVERTERS, SensorDeviceClass
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)

# The unit the user typed for a custom PID, lower case -> device class and
# Home Assistant unit. With a device class Home Assistant can convert the unit
# and draw the right graph. Anything else keeps the user's text, with no
# device class: a device class with a unit it does not know is an error.
_CUSTOM_UNITS: dict[str, tuple[SensorDeviceClass | None, str]] = {
    "%": (None, PERCENTAGE),
    "°c": (SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS),
    "°f": (SensorDeviceClass.TEMPERATURE, UnitOfTemperature.FAHRENHEIT),
    "v": (SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
    "mv": (SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.MILLIVOLT),
    "a": (SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
    "ma": (SensorDeviceClass.CURRENT, UnitOfElectricCurrent.MILLIAMPERE),
    "w": (SensorDeviceClass.POWER, UnitOfPower.WATT),
    "kw": (SensorDeviceClass.POWER, UnitOfPower.KILO_WATT),
    "wh": (SensorDeviceClass.ENERGY_STORAGE, UnitOfEnergy.WATT_HOUR),
    "kwh": (SensorDeviceClass.ENERGY_STORAGE, UnitOfEnergy.KILO_WATT_HOUR),
    "pa": (SensorDeviceClass.PRESSURE, UnitOfPressure.PA),
    "hpa": (SensorDeviceClass.PRESSURE, UnitOfPressure.HPA),
    "kpa": (SensorDeviceClass.PRESSURE, UnitOfPressure.KPA),
    "mbar": (SensorDeviceClass.PRESSURE, UnitOfPressure.MBAR),
    "bar": (SensorDeviceClass.PRESSURE, UnitOfPressure.BAR),
    "psi": (SensorDeviceClass.PRESSURE, UnitOfPressure.PSI),
    "km/h": (SensorDeviceClass.SPEED, UnitOfSpeed.KILOMETERS_PER_HOUR),
    "mph": (SensorDeviceClass.SPEED, UnitOfSpeed.MILES_PER_HOUR),
    "m": (SensorDeviceClass.DISTANCE, UnitOfLength.METERS),
    "km": (SensorDeviceClass.DISTANCE, UnitOfLength.KILOMETERS),
    "mi": (SensorDeviceClass.DISTANCE, UnitOfLength.MILES),
    "l": (SensorDeviceClass.VOLUME_STORAGE, UnitOfVolume.LITERS),
    "s": (SensorDeviceClass.DURATION, UnitOfTime.SECONDS),
    "min": (SensorDeviceClass.DURATION, UnitOfTime.MINUTES),
    "h": (SensorDeviceClass.DURATION, UnitOfTime.HOURS),
    "g": (SensorDeviceClass.WEIGHT, UnitOfMass.GRAMS),
    "kg": (SensorDeviceClass.WEIGHT, UnitOfMass.KILOGRAMS),
    "rpm": (None, REVOLUTIONS_PER_MINUTE),
}


def custom_unit(unit: str | None) -> tuple[SensorDeviceClass | None, str | None]:
    """Device class and unit of a custom PID, from the unit typed in the app."""
    if not unit:
        return None, None
    return _CUSTOM_UNITS.get(unit.lower(), (None, unit))


# The built-in sensors a custom PID can stand in for, with their unit, in the
# order of the options form. For a car whose standard reading is wrong (a
# battery charge always 0) while a custom PID reads it right. The trouble
# codes are not here: they are a count with a list, not one number.
SOURCE_UNITS: dict[str, str] = {
    "battery_level": PERCENTAGE,
    "fuel_level": PERCENTAGE,
    "range": UnitOfLength.KILOMETERS,
    "odometer": UnitOfLength.KILOMETERS,
    "battery_voltage": UnitOfElectricPotential.VOLT,
    "coolant_temperature": UnitOfTemperature.CELSIUS,
    "fuel_volume": UnitOfVolume.LITERS,
    "speed": UnitOfSpeed.KILOMETERS_PER_HOUR,
    "engine_speed": REVOLUTIONS_PER_MINUTE,
}


def fits(unit: str | None, target: str) -> bool:
    """Whether a custom PID with this unit can stand in for a sensor in target.

    The same unit, or one Home Assistant converts to it, fits. So do no unit
    and a unit Home Assistant does not know: the user typed it, the user
    knows. A known unit of another kind (°C for a battery charge) does not.
    """
    device_class, known = custom_unit(unit)
    if not unit or known == target or unit.lower() not in _CUSTOM_UNITS:
        return True
    converter = UNIT_CONVERTERS.get(device_class) if device_class else None
    return converter is not None and target in converter.VALID_UNITS


def convert(value: float | int, unit: str | None, target: str) -> float | int:
    """A custom PID's value in the unit of the sensor it stands in for."""
    device_class, known = custom_unit(unit)
    converter = UNIT_CONVERTERS.get(device_class) if device_class else None
    if known is None or known == target or converter is None:
        return value
    if target not in converter.VALID_UNITS:
        return value
    return round(converter.convert(value, known, target), 3)
