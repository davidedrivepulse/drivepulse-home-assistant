# Supported OBD2 adapters

The DrivePulse app reads your car through an OBD2 adapter plugged into the diagnostic port. This integration never talks to the adapter: the app does, and then sends the results to Home Assistant over your network. So the adapter question is really "what does the app need?". This page answers it.

## What the app needs

An adapter that speaks the **ELM327 command set**: a genuine ELM327 or a compatible chip, version 1.5 or later.

| Connection | iPhone | Android |
|---|---|---|
| Bluetooth Low Energy (BLE, often labelled "Bluetooth 4.0" or "Low Energy") | Yes | Yes |
| Wi-Fi | Yes | Yes |
| Classic Bluetooth (non-BLE) | No | Yes |

- **BLE**: no pairing in the phone's Bluetooth settings. Connect from the app: *Settings → OBD2 Adapter → Search devices*. The manual search shows every device nearby. Background reconnection looks for the services the common OBD dongles advertise: `18F0` (Vgate / vLinker), `FFF0`, `FFE0` and `FFE5`.
- **Wi-Fi**: first join the adapter's own Wi-Fi network in the phone settings, then choose Wi-Fi in the app and tap Connect. The default address is `192.168.0.10`, port `35000`. Presets are also offered for `192.168.0.11:35000`, `192.168.4.1:35000` and port `23`.
- **Classic Bluetooth (Android only)**: pair the adapter in the phone's Bluetooth settings first, then tap Search devices in the app. It shows up with the *Classic Bluetooth* label.

## Vehicle protocols

The app starts with the adapter's automatic protocol search. If the car does not answer, it tries the OBD2 protocols one by one, in this order:

1. ISO 15765-4 CAN, 11-bit, 500 kbaud
2. ISO 15765-4 CAN, 29-bit, 500 kbaud
3. CAN 11-bit, 250 kbaud
4. CAN 29-bit, 250 kbaud
5. ISO 14230-4 KWP2000, fast init
6. ISO 14230-4 KWP2000, 5-baud init
7. ISO 9141-2
8. SAE J1850 PWM
9. SAE J1850 VPW

The protocol that works is remembered for the next connection. SAE J1939 (trucks) is not used.

- **OBD on UDS (SAE J1979-2)**, used by US cars from model year 2027: from app version 3.6.2, live data and the VIN are read through the UDS identifiers. Fault code reading on these cars is marked as incomplete.
- **Cars without standard OBD data** (mode 01, missing on some electric cars): trips, distance and parking still work, but engine values and diagnostics do not.

## Recommended adapters

Two brands, both working over BLE on iPhone and Android:

- **Veepeak OBDCheck BLE or BLE+**. DrivePulse is in Veepeak's own list of compatible apps. Veepeak advises unplugging these models if the car will sit for more than a week.
- **Vgate iCar Pro 2S**. It switches itself off when the engine is off, so it can stay plugged in.

Ford and Mazda owners who also use other car programs can take the **Vgate vLinker FD+**: DrivePulse reads the same data with it.

The **OBDLink MX+** works on Android. It uses classic Bluetooth, so it does not work with DrivePulse on iPhone.

## What does not work

- **Proprietary dongles** such as OBDeleven, Carly or the VW DataPlug. They only work with their makers' apps. When one connects, DrivePulse says it is not an ELM327 adapter.
- **Classic Bluetooth adapters on iPhone**. iPhone does not support them, the OBDLink MX+ included. Use a BLE or Wi-Fi adapter.
- **Very cheap clones sold as "ELM327 v2.1"** are hit and miss. Many of them reject some setup commands or cut long replies short, and then the VIN and some make-specific data do not arrive.

## How to tell if an adapter works

1. Plug the adapter into the OBD2 port, usually under the steering wheel, and turn the ignition on.
2. Connect it from the app as described above for BLE, Wi-Fi or classic Bluetooth.
3. While connecting, the app examines the adapter's replies:
   - **"Your adapter has some limits"** means the adapter rejects some configuration commands or cuts long replies short. The app says which ones. You can keep using it, but some readings may be slower or missing.
   - **"It is not an ELM327 adapter"** means the device connected but does not answer standard OBD2 commands (see *Proprietary dongles* above).
4. If *Live data* shows engine speed and coolant temperature, the adapter works. The Home Assistant sensors then fill in as the app sends its data.

## Power use when parked

- The Vgate iCar Pro 2S switches itself off with the engine.
- Veepeak advises unplugging if the car will sit for more than a week.
- Wi-Fi adapters draw more in standby. Unplug them if you will not drive for days.

## In Home Assistant

The entities you get depend on what your car answers through the adapter, not on the adapter brand. For example, *Range* appears only when the car reports it. The VIN is never sent to Home Assistant, whatever the adapter.
