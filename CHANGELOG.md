# Changelog

## 0.3.0

- New sensor **Odometer (estimate)**: the DrivePulse app's own estimate of the odometer, the km you typed in the app (or the car gave once) plus the trips since. It appears with the first message from DrivePulse 3.6.3 or later that has a number.
- **Odometer** is now only the car's own reading. Up to app 3.6.2 it took the app's estimate at the end of a trip when the car gave nothing, so on cars where the two differ the sensor jumped back and forth and `utility_meter` broke (#6). With DrivePulse 3.6.3, a value that came from an older app (it may be an estimate) is dropped at the first message: **Odometer** is then unavailable until the car gives a reading, and keeps the car's last reading from then on. If your car never gives its odometer, use **Odometer (estimate)** in your automations and dashboards.
- **Odometer (estimate)** can go down (you correct the km in the app, or delete a trip): its state class is `total`, so the statistics follow the change instead of starting a new cycle. A `utility_meter` on it ignores a drop by default.
- The trip events carry `trip.odometer_source`: where `trip.odometer_km` comes from (`cluster`, `cluster_end`, `app`, or null).
- The trip events carry `odometer_estimated_km`.
- Message format: [schema/drivepulse-schema-2.json](schema/drivepulse-schema-2.json), sent by DrivePulse 3.6.3 or later. Apps up to 3.6.2 send schema 1, which keeps working.

Earlier versions: see the [releases](https://github.com/davidedrivepulse/drivepulse-home-assistant/releases).
