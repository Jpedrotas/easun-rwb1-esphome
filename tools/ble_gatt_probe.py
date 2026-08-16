"""Read-only BLE GATT service enumerator.

Usage:
    python tools/ble_gatt_probe.py BLE_ADDRESS

The address is only used for the connection and is never printed.
"""

from __future__ import annotations

import argparse
import asyncio

from bleak import BleakClient


async def probe(address: str) -> None:
    async with BleakClient(address, timeout=20.0) as client:
        print("Connected: yes")
        for service in client.services:
            print(f"Service {service.uuid}")
            for characteristic in service.characteristics:
                properties = ",".join(characteristic.properties)
                print(
                    f"  Handle 0x{characteristic.handle:04x} "
                    f"characteristic {characteristic.uuid} [{properties}]"
                )
                for descriptor in characteristic.descriptors:
                    print(
                        f"    Handle 0x{descriptor.handle:04x} "
                        f"descriptor {descriptor.uuid}"
                    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("address", help="BLE address; never stored or displayed")
    args = parser.parse_args()
    asyncio.run(probe(args.address))


if __name__ == "__main__":
    main()
