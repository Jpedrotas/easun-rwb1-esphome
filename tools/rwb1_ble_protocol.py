"""Dependency-free helpers for the read-only RWB1 BLE transport."""

from __future__ import annotations

import hashlib
import os

MAX_FRAGMENT_PAYLOAD = 227


def fragment_payload(payload: bytes) -> list[bytes]:
    """Wrap a payload in the RWB1 three-byte transport header."""
    if not payload or len(payload) > MAX_FRAGMENT_PAYLOAD * 255:
        raise ValueError("unsupported payload length")
    fragments = [
        payload[offset : offset + MAX_FRAGMENT_PAYLOAD]
        for offset in range(0, len(payload), MAX_FRAGMENT_PAYLOAD)
    ]
    total = len(fragments)
    return [bytes((index, total, len(chunk))) + chunk for index, chunk in enumerate(fragments, 1)]


def consume_fragment(fragment: bytes, chunks: dict[int, bytes]) -> bytes | None:
    """Validate and reassemble an RWB1 message, returning it when complete."""
    if len(fragment) < 3:
        return None
    index, total, length = fragment[:3]
    data = fragment[3:]
    if index == 0 or total == 0 or index > total or length != len(data):
        return None
    if index == 1:
        chunks.clear()
    chunks[index] = data
    if len(chunks) != total or any(part not in chunks for part in range(1, total + 1)):
        return None
    return b"".join(chunks[part] for part in range(1, total + 1))


def derive_key(dtu_id: str | None) -> bytes:
    """Derive the application key, with a private diagnostic override."""
    override = os.environ.get("RWB1_AES_KEY_HEX")
    if override:
        key = bytes.fromhex(override)
        if len(key) != 16:
            raise ValueError("RWB1_AES_KEY_HEX must contain exactly 16 bytes")
        return key
    if not dtu_id:
        raise ValueError("provide --dtu-id or set RWB1_DTU_ID")
    return hashlib.md5((dtu_id.strip() + "SEC_").encode("utf-8")).digest()


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc
