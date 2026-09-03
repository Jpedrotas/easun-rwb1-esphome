# EASUN RWB1 ESPHome

> Unofficial community project. It is not affiliated with or endorsed by
> EASUN, the RWB1 manufacturer or the vendor application provider.

> Status: initial stable release. Direct BLE telemetry and Wi-Fi/BLE
> coexistence are validated on the tested ESP32-C3 configuration.

[`esphome/rwb1_ble.yaml`](esphome/rwb1_ble.yaml) is the ready-to-use ESP32-C3
configuration. It discovers the
nearby RWB1 from its `SSL_` Bluetooth name, keeps one BLE connection open and
publishes the confirmed read-only telemetry block to Home Assistant. No MAC
address or inverter-control entity is required.

## Quick start

1. In the ESPHome dashboard, create a new ESP32-C3 device. This creates the
   Wi-Fi, API and OTA values in its private `secrets.yaml`.
2. Copy `esphome/rwb1_ble.yaml` over the generated device configuration.
3. Find the RWB1 **DTU ID** in the vendor application. Depending on the app and
   version, the same identifier may be labelled **Device PN** or **Device
   Name**. Use the instructions in [How to find the DTU ID](#how-to-find-the-dtu-id),
   then add it only to the ESPHome secrets file:

   ```yaml
   rwb1_dtu_id: "YOUR_RWB1_DTU_ID"
   ```

4. Connect the ESP32-C3 by USB for the first installation and choose **Install**.
5. Place it within reliable Bluetooth range of the RWB1. The activity LED blinks
   for each request fragment and each valid response.

Do not publish `secrets.yaml`, generated build directories, ESPHome diagnostic
bundles, DTU IDs or Bluetooth addresses. The DTU ID is used locally to derive
the protocol key and is compiled into the firmware; protect firmware backups as
private data too.

The supplied example uses a two-second update interval. This cadence completed
repeated live reads on the confirmed test system. If another RWB1 revision is
unstable or Wi-Fi/Bluetooth coexistence is poor, change the substitution to
`5s`, `10s` or `30s` before assuming incompatibility.

The production example deliberately keeps BLE scanning stopped until Wi-Fi and
the native Home Assistant API are connected, then uses a low-duty-cycle passive
scan.
Wi-Fi and Bluetooth share the single-core ESP32-C3 radio; starting BLE earlier
can prevent Wi-Fi from authenticating on mesh or multi-access-point networks.
It also defaults to `wifi_output_power: 8.5dB`. This setting fixed repeated
`Auth Expired` errors on the tested ESP32-C3 while retaining reliable network
coverage. It can be overridden in `substitutions` if a different board or site
needs more transmit power.
The RWB1 is still discovered automatically, normally within a few seconds after
the API connection is established. If the last API client disconnects, scanning
is stopped again so the node can recover its network connection cleanly.

Only one local BLE client may be able to connect at a time. Close the vendor
application's Bluetooth Tool while ESPHome is connected. The RWB1's normal
Wi-Fi/cloud path is separate from this local BLE connection.

## How to find the DTU ID

The easiest and safest method is to copy it from the vendor application. The
same identifier is not labelled consistently across applications: look for
**DTU ID**, **Device PN** or **Device Name**. The tested application displays
its menus in English, but translated versions may use equivalent names.

1. Open the vendor application and sign in to the account that owns the EASUN
   installation.
2. On the home/device screen, open the EASUN installation or datalogger.
3. Open **Device Information**. Depending on the application version, this may
   be reached through the information/details button or the menu in the top
   corner of the device page.
4. Locate the row labelled **DTU ID**, **Device PN** or **Device Name**.
5. Tap the copy icon beside that row. Copy the complete value without spaces,
   line breaks or added punctuation.
6. In the ESPHome dashboard, open `secrets.yaml` and add:

   ```yaml
   rwb1_dtu_id: "PASTE_THE_COMPLETE_DTU_ID_HERE"
   ```

The required value is normally a long identifier, even when the application
calls it **Device Name**. Do not use an editable friendly name or installation
nickname. It is **not** any of the following:

- the value shown on the **SN** row;
- the Bluetooth name beginning with `SSL_`;
- a Bluetooth MAC address containing colons;
- the inverter model, Wi-Fi password or account password.

The **ME → Bluetooth Tool** screen is useful for confirming that the RWB1 can be
found over Bluetooth, but it is not required to copy the DTU ID. Do not guess a
DTU ID from the `SSL_` name or from a physical label: copy the complete value
shown as **DTU ID**, **Device PN** or **Device Name** in the application.

If **Device Information**, **DTU ID**, **Device PN** or **Device Name** is not
visible, confirm that the device has been added to the signed-in account and
that the account has permission to view it. Application layouts can change;
look for **Information**, **Details** or an information icon on the device
page. Do not share screenshots of this page publicly because they may also
contain serial numbers, location and other private installation data.

If ESPHome discovers and connects to the RWB1 but repeatedly logs `Invalid RWB1
response`, re-copy the DTU ID and check for missing digits or spaces. A wrong DTU
ID derives the wrong local key, so the encrypted response cannot be decoded.

## Different ESP32-C3 boards

The tested board has a 4 MB flash and an active-low LED on GPIO8. Change
`activity_led_pin` when the board uses another pin. Remove the complete
`activity_led` block if no suitable LED is available. Do not guess pins on
boards with an RGB LED or other peripherals attached to GPIO8.

## Discovery-only diagnostic

`esphome/rwb1_ble_diagnostic.yaml` is a small read-only build with no Wi-Fi, API, OTA,
device MAC, DTU ID or control actions. It only scans for the `SSL_` name prefix
and blinks the common GPIO8 LED when advertisements are seen:

```console
esphome run esphome/rwb1_ble_diagnostic.yaml --device COM3
```

The diagnostic is useful when the final component reports that no RWB1 was
found. It does not read telemetry.
