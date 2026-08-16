# Security

The RWB1 DTU ID is used locally to derive the Bluetooth protocol key. Never
publish a real DTU ID, `secrets.yaml`, compiled firmware, diagnostic bundles,
Bluetooth addresses, packet captures or complete device logs.

This project exposes read-only telemetry and does not provide inverter control
entities. Any future write support must be opt-in, allow-listed and tested.

Use GitHub private vulnerability reporting for security issues. Do not open a
public issue containing real device identifiers or credentials.

