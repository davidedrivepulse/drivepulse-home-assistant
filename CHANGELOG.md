# Changelog

## 0.3.0

- New sensor **Odometer (estimate)**: the DrivePulse app's own estimate of the odometer, the km you typed in the app (or the car gave once) plus the trips since. It appears with the first message from DrivePulse 3.6.3 or later that has a number.
- **Odometer** is now only the car's own reading. Up to app 3.6.2 it took the app's estimate at the end of a trip when the car gave nothing, so on cars where the two differ the sensor jumped back and forth and `utility_meter` broke (#6). If your car never gives its odometer, **Odometer** keeps its last value: use **Odometer (estimate)** in your automations and dashboards.
- The trip events carry `odometer_estimated_km`.
- Message format: [schema/drivepulse-schema-2.json](schema/drivepulse-schema-2.json), sent by DrivePulse 3.6.3 or later. Apps up to 3.6.2 send schema 1, which keeps working.

Earlier versions: see the [releases](https://github.com/davidedrivepulse/drivepulse-home-assistant/releases).
