"""Perform one allow-listed, read-only Modbus telemetry query over RWB1 BLE.

Only function 0x03, slave 5, start register 0x1195 and 21 registers are
implemented here intentionally. The Bluetooth address is not logged.

The tested RWB1 uses a private three-byte fragmentation header:
``fragment number``, ``total fragments``, ``payload length``. Fragment numbers
start at one. This differs from the four-byte Alibaba AIS packet header despite
the reused FED5/FED6 characteristic UUIDs.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import secrets
import string

from bleak import BleakClient, BleakScanner
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

try:
    from tools.rwb1_ble_protocol import (
        MAX_FRAGMENT_PAYLOAD,
        consume_fragment,
        crc16_modbus,
        derive_key,
        fragment_payload,
    )
except ModuleNotFoundError:  # Direct execution from the tools directory.
    from rwb1_ble_protocol import (
        MAX_FRAGMENT_PAYLOAD,
        consume_fragment,
        crc16_modbus,
        derive_key,
        fragment_payload,
    )

SERVICE_UUID = "0000fee7-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000fed5-0000-1000-8000-00805f9b34fb"
INDICATE_UUID = "0000fed6-0000-1000-8000-00805f9b34fb"
READ_REQUEST = bytes.fromhex("05 03 11 95 00 15 90 91")
def encrypt_request(request: bytes, key: bytes) -> bytes:
    cmd_no = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(4))
    envelope = {
        "CID": 30024,
        "PL": {
            "Req": request.hex().upper(),
            "Uart": {"BaudRate": 2400, "DataBit": 8, "ParityBit": "NONE", "StopBit": 1},
            "CmdType": "gatherSingleDevProps",
            "CmdNo": cmd_no,
        },
    }
    plaintext = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
    plaintext += b"\0" * (16 - len(plaintext) % 16)
    encryptor = Cipher(algorithms.AES(key), modes.CBC(key)).encryptor()
    return base64.b64encode(encryptor.update(plaintext) + encryptor.finalize())


def decrypt_response(message: bytes, key: bytes) -> bytes:
    ciphertext = base64.b64decode(message, validate=True)
    if not ciphertext or len(ciphertext) % 16:
        raise ValueError("invalid encrypted response length")
    decryptor = Cipher(algorithms.AES(key), modes.CBC(key)).decryptor()
    plaintext = (decryptor.update(ciphertext) + decryptor.finalize()).rstrip(b"\0")
    envelope = json.loads(plaintext.decode("utf-8"))
    if envelope.get("CID") != 30025 or envelope.get("RC") != 0:
        raise ValueError("unexpected RWB1 response")
    response = bytes.fromhex(envelope["PL"]["Rsp"])
    if len(response) < 5:
        raise ValueError("Modbus response is too short")
    return response


async def read_telemetry(address: str, timeout: float, key: bytes) -> None:
    chunks: dict[int, bytes] = {}
    messages: list[bytes] = []
    received = asyncio.Event()

    def on_data(_characteristic: object, data: bytearray) -> None:
        message = consume_fragment(bytes(data), chunks)
        print(f"RX fragment: {len(data)} bytes")
        if message is not None:
            messages.append(message)
            print(f"Complete RX message: {len(message)} bytes")
            received.set()

    async with BleakClient(address, timeout=20.0) as client:
        service = client.services.get_service(SERVICE_UUID)
        if service is None:
            raise RuntimeError("FEE7 service not found")
        await client.start_notify(INDICATE_UUID, on_data)
        max_payload = max(1, min(MAX_FRAGMENT_PAYLOAD, client.mtu_size - 6))
        encrypted_request = encrypt_request(READ_REQUEST, key)
        fragments = [
            encrypted_request[offset : offset + max_payload]
            for offset in range(0, len(encrypted_request), max_payload)
        ]
        total = len(fragments)
        for index, payload in enumerate(fragments, 1):
            fragment = bytes((index, total, len(payload))) + payload
            print(f"TX fragment: {len(fragment)} bytes")
            await client.write_gatt_char(WRITE_UUID, fragment, response=True)
        try:
            await asyncio.wait_for(received.wait(), timeout=timeout)
            await asyncio.sleep(1.0)
        except asyncio.TimeoutError:
            print("No response before timeout")
        finally:
            await client.stop_notify(INDICATE_UUID)
    if not messages:
        print("Messages received: 0")
        return
    response = decrypt_response(messages[-1], key)
    expected_crc = int.from_bytes(response[-2:], "little")
    if crc16_modbus(response[:-2]) != expected_crc:
        raise ValueError("invalid Modbus CRC")
    if response[0] != READ_REQUEST[0] or response[1] != READ_REQUEST[1]:
        raise ValueError("unexpected Modbus function or address")
    print(f"Read validated: {response[2] // 2} registers, CRC valid")


async def find_by_name_prefix(prefix: str) -> str:
    """Find one nearby device without printing or persisting its address."""
    devices = await BleakScanner.discover(timeout=8.0, return_adv=True)
    matches = [
        device.address
        for device, advertisement in devices.values()
        if (advertisement.local_name or "").startswith(prefix)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one device with prefix {prefix!r}; found {len(matches)}")
    return matches[0]


async def run(address: str | None, prefix: str, timeout: float, dtu_id: str | None) -> None:
    key = derive_key(dtu_id or os.environ.get("RWB1_DTU_ID"))
    await read_telemetry(address or await find_by_name_prefix(prefix), timeout, key)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("address", nargs="?", help="BLE address; never stored or displayed")
    parser.add_argument("--name-prefix", default="SSL_", help="BLE prefix used when the address is omitted")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--dtu-id", help="DTU identifier; RWB1_DTU_ID can also be used")
    args = parser.parse_args()
    asyncio.run(run(args.address, args.name_prefix, args.timeout, args.dtu_id))


if __name__ == "__main__":
    main()
