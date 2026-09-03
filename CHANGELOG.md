# Changelog

All notable changes to this project are documented here.

## Unreleased

- Documented that vendor applications may label the required DTU ID as
  `Device PN` or `Device Name`.
- Added an original illustrated hardware overview of the inverter, RWB1-04
  dongle and ESP32-C3 board to the installation documentation.

## 0.1.0 - 2026-08-16

- Added the tested ESP32-C3 Wi-Fi settings: disabled power saving and an 8.5 dB
  transmit-power default to avoid repeated WPA2 `Auth Expired` failures.
- Confirmed simultaneous Wi-Fi and BLE operation with repeated validated
  two-second telemetry reads on the reference hardware.

## 0.1.0-alpha.1 - 2026-08-16

- Initial standalone ESPHome external component for direct RWB1 BLE telemetry.
- Added ESP32-C3 example, read-only sensors and two-second polling.
- Added automatic `SSL_` discovery, local key derivation and CRC validation.
- Added activity LED support and diagnostic configuration.
- Added public documentation without device identifiers or credentials.
