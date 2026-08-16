"""Tests for the public, read-only RWB1 BLE protocol helpers."""

import hashlib
import os
import unittest
from unittest.mock import patch

from tools.rwb1_ble_protocol import (
    MAX_FRAGMENT_PAYLOAD,
    consume_fragment,
    crc16_modbus,
    derive_key,
    fragment_payload,
)


class BLEProtocolTests(unittest.TestCase):
    def test_fragment_round_trip(self) -> None:
        payload = bytes(range(256)) * 2
        fragments = fragment_payload(payload)
        self.assertEqual(len(fragments), 3)
        self.assertTrue(all(len(fragment) <= MAX_FRAGMENT_PAYLOAD + 3 for fragment in fragments))

        chunks: dict[int, bytes] = {}
        complete = None
        for fragment in fragments:
            complete = consume_fragment(fragment, chunks)
        self.assertEqual(complete, payload)

    def test_invalid_fragment_is_rejected(self) -> None:
        self.assertIsNone(consume_fragment(b"\x01\x01\x02x", {}))

    def test_confirmed_read_request_crc(self) -> None:
        request_without_crc = bytes.fromhex("05 03 11 95 00 15")
        self.assertEqual(crc16_modbus(request_without_crc), 0x9190)

    def test_key_derivation_uses_private_dtu_id(self) -> None:
        synthetic_id = "PUBLIC-TEST-ONLY"
        with patch.dict(os.environ, {}, clear=True):
            derived = derive_key(synthetic_id)
        expected = hashlib.md5((synthetic_id + "SEC_").encode()).digest()
        self.assertEqual(derived, expected)


if __name__ == "__main__":
    unittest.main()
