# Compatibility

## Confirmed test system

| Layer | Confirmed configuration |
|---|---|
| Inverter | EASUN iSolar SMH III 4.2 kW |
| Datalogger | Solar Plug-RWB1, type 04 |
| ESP32 | ESP32-C3 development board, 4 MB flash |
| ESPHome | 2026.7.4 with ESP-IDF 5.5.5 |
| Home Assistant host | Raspberry Pi 4, 2 GB RAM |
| Telemetry | 21-register read-only block, CRC validated |
| Polling | Repeated two-second reads confirmed over BLE |

Other RWB1 firmware revisions and related inverter models are unconfirmed.
Report compatibility without publishing DTU IDs, MAC addresses, serial numbers,
private network addresses or complete logs.

