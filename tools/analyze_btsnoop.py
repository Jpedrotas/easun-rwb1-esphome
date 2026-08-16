"""Validate read-only RWB1 BLE traffic captured in an Android btsnoop file.

The utility deliberately prints only protocol structure. Device identifiers,
Bluetooth addresses, cryptographic material and telemetry values are omitted.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import struct
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

ATT_CID = 0x0004
ATT_WRITE_OPCODES = {0x12, 0x52, 0xD2}
ATT_RECEIVE_OPCODES = {0x1B, 0x1D}
WRITE_VALUE_HANDLE = 0x0016
INDICATE_VALUE_HANDLE = 0x0013


def iter_btsnoop_records(path: Path) -> Iterator[tuple[int, bytes]]:
    with path.open("rb") as capture:
        header = capture.read(16)
        if len(header) != 16 or header[:8] != b"btsnoop\0":
            raise ValueError("invalid btsnoop file")
        while record_header := capture.read(24):
            if len(record_header) != 24:
                raise ValueError("truncated btsnoop header")
            original_length, included_length, flags, _drops, _timestamp = struct.unpack(
                ">IIIIQ", record_header
            )
            packet = capture.read(included_length)
            if len(packet) != included_length:
                raise ValueError("truncated btsnoop record")
            if included_length != original_length:
                continue
            yield flags & 1, packet


def iter_att_pdus(path: Path) -> Iterator[tuple[int, bytes]]:
    continuations: dict[tuple[int, int], tuple[int, int, bytearray]] = {}
    for direction, packet in iter_btsnoop_records(path):
        if len(packet) < 5 or packet[0] != 0x02:
            continue
        handle_flags, acl_length = struct.unpack_from("<HH", packet, 1)
        acl = packet[5 : 5 + acl_length]
        handle = handle_flags & 0x0FFF
        pb_flag = (handle_flags >> 12) & 0x03
        key = direction, handle
        if pb_flag in (0, 2):
            if len(acl) < 4:
                continue
            l2cap_length, cid = struct.unpack_from("<HH", acl)
            expected = l2cap_length
            continuations[key] = (cid, expected, bytearray(acl[4:]))
        elif pb_flag == 1 and key in continuations:
            cid, expected, data = continuations[key]
            data.extend(acl)
        else:
            continue
        cid, expected, data = continuations[key]
        if len(data) >= expected:
            del continuations[key]
            if cid == ATT_CID:
                yield direction, bytes(data[:expected])


def extract_messages(path: Path) -> list[tuple[str, bytes]]:
    chunks: dict[str, dict[int, bytes]] = {"TX": {}, "RX": {}}
    messages: list[tuple[str, bytes]] = []
    for direction, pdu in iter_att_pdus(path):
        if len(pdu) < 3:
            continue
        opcode = pdu[0]
        value_handle = int.from_bytes(pdu[1:3], "little")
        if opcode in ATT_WRITE_OPCODES and value_handle == WRITE_VALUE_HANDLE:
            label = "TX"
        elif opcode in ATT_RECEIVE_OPCODES and value_handle == INDICATE_VALUE_HANDLE:
            label = "RX"
        else:
            continue
        fragment = pdu[3:]
        if len(fragment) < 3:
            continue
        index, total, length = fragment[:3]
        payload = fragment[3:]
        if not index or not total or index > total or length != len(payload):
            continue
        if index == 1:
            chunks[label].clear()
        chunks[label][index] = payload
        if len(chunks[label]) == total and all(i in chunks[label] for i in range(1, total + 1)):
            messages.append((label, b"".join(chunks[label][i] for i in range(1, total + 1))))
            chunks[label].clear()
    return messages


def derive_key(dtu_id: str | None) -> bytes:
    """Derive the capture key without logging the private DTU identifier."""
    override = os.environ.get("RWB1_AES_KEY_HEX")
    if override:
        key = bytes.fromhex(override)
        if len(key) != 16:
            raise ValueError("RWB1_AES_KEY_HEX must contain exactly 16 bytes")
        return key
    if not dtu_id:
        raise ValueError("provide --dtu-id or set RWB1_DTU_ID")
    return hashlib.md5((dtu_id.strip() + "SEC_").encode("utf-8")).digest()


def decrypt_message(message: bytes, keys: list[bytes]) -> Any:
    ciphertext = base64.b64decode(message, validate=True)
    for key in keys:
        if ciphertext and len(ciphertext) % 16 == 0:
            decryptor = Cipher(algorithms.AES(key), modes.CBC(key)).decryptor()
            plaintext = (decryptor.update(ciphertext) + decryptor.finalize()).rstrip(b"\0")
            try:
                return json.loads(plaintext.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass

        # GCM messages carry an eight-byte random nonce suffix, a 16-byte tag
        # and the ciphertext. The first half of the nonce is key-derived.
        if len(ciphertext) > 24:
            nonce = key[:8] + ciphertext[:8]
            tag = ciphertext[8:24]
            encrypted = ciphertext[24:]
            try:
                plaintext = AESGCM(key).decrypt(nonce, encrypted + tag, None).rstrip(b"\0")
                return json.loads(plaintext.decode("utf-8"))
            except Exception:
                pass
    raise ValueError("could not authenticate/decode the message")


def describe(value: Any) -> str:
    if isinstance(value, dict):
        keys = ", ".join(sorted(str(key) for key in value))
        cid = value.get("CID")
        cid_text = f", CID={cid}" if isinstance(cid, int) else ""
        return f"object({keys}{cid_text})"
    if isinstance(value, list):
        return f"list[{len(value)}]"
    return type(value).__name__


def run(path: Path, dtu_id: str | None) -> None:
    keys = [derive_key(dtu_id or os.environ.get("RWB1_DTU_ID"))]
    messages = extract_messages(path)
    decoded = [(direction, decrypt_message(payload, keys)) for direction, payload in messages]
    print(f"Complete messages: {len(decoded)}")
    for index, (direction, value) in enumerate(decoded, 1):
        print(f"{index:03d} {direction}: {describe(value)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--dtu-id", help="DTU identifier; RWB1_DTU_ID can also be used")
    args = parser.parse_args()
    run(args.capture, args.dtu_id)


if __name__ == "__main__":
    main()
