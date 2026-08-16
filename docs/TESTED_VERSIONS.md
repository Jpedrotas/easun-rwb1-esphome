# Tested versions

## Confirmed environment

| Component | Version or platform |
|---|---|
| Inverter | EASUN iSolar SMH III 4.2 kW |
| Datalogger | Solar Plug-RWB1, type 04 |
| ESP32 board | ESP32-C3 development board, 4 MB flash |
| ESPHome board definition | `esp32-c3-devkitm-1` |
| ESPHome | 2026.7.4 |
| ESP-IDF | 5.5.5 |
| Home Assistant Core | 2026.8.1 |
| Home Assistant OS | 18.2 |
| Home Assistant Supervisor | 2026.07.5 |
| Home Assistant hardware | Raspberry Pi 4 with 2 GB RAM |

Direct BLE discovery, connection, response decryption, Modbus CRC validation
and repeated two-second telemetry reads were confirmed on this environment.
Wi-Fi and BLE coexistence on the final `esp32-c3-devkitm-1` configuration is
being validated before the first stable release.

When reporting another working configuration, include the ESP32 board, flash
size, ESPHome version, RWB1 type and read cadence. Do not include DTU IDs, MAC
addresses, serial numbers, private addresses, credentials or complete logs.

