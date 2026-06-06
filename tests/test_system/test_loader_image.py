# Linker tarafından üretilen .picoimg formatının entry adresi, segment adresleri,
# izinleri, verileri ve CRC32 alanlarını doğru taşıdığını ve doğruladığını test eder.

import os
import tempfile
import unittest

from src.loader_image import (
    FLAG_EXECUTE,
    FLAG_READ,
    FLAG_WRITE,
    LoaderImageError,
    decode_loader_image,
    encode_loader_image,
    read_loader_image,
    write_loader_image,
)


class LoaderImageTests(unittest.TestCase):
    def test_round_trip_preserves_entry_addresses_flags_and_data(self):
        encoded = encode_loader_image(
            0x100,
            [
                {"address": 0x100, "flags": FLAG_READ | FLAG_EXECUTE, "data": b"\x13\x00\x00\x00"},
                {"address": 0x2000, "flags": FLAG_READ | FLAG_WRITE, "data": b"\x2A\x00\x00\x00"},
            ],
        )

        decoded = decode_loader_image(encoded)

        self.assertEqual(0x100, decoded["entry"])
        self.assertEqual([0x100, 0x2000], [segment["address"] for segment in decoded["segments"]])
        self.assertEqual(
            [FLAG_READ | FLAG_EXECUTE, FLAG_READ | FLAG_WRITE],
            [segment["flags"] for segment in decoded["segments"]],
        )
        self.assertEqual(
            [b"\x13\x00\x00\x00", b"\x2A\x00\x00\x00"],
            [segment["data"] for segment in decoded["segments"]],
        )

    def test_corrupted_image_crc_is_rejected(self):
        encoded = bytearray(
            encode_loader_image(
                0,
                [{"address": 0, "flags": FLAG_READ | FLAG_EXECUTE, "data": b"\x73\x00\x10\x00"}],
            )
        )
        encoded[-1] ^= 0xFF

        with self.assertRaisesRegex(LoaderImageError, "image CRC32"):
            decode_loader_image(bytes(encoded))

    def test_overlapping_segments_are_rejected(self):
        with self.assertRaisesRegex(LoaderImageError, "çakışıyor"):
            encode_loader_image(
                0,
                [
                    {"address": 0, "flags": FLAG_READ, "data": b"\x00" * 8},
                    {"address": 4, "flags": FLAG_WRITE, "data": b"\x00" * 4},
                ],
            )

    def test_linked_object_is_written_and_read_as_single_image(self):
        linked = {
            "entry": 0,
            "memory_regions": [
                {
                    "name": "ROM",
                    "flags": "rx",
                    "origin": 0,
                    "memory_words": ["0x00100073"],
                },
                {
                    "name": "RAM",
                    "flags": "rw",
                    "origin": 0x10000,
                    "memory_words": ["0x12345678"],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "program.picoimg")
            written = write_loader_image(linked, path)
            decoded = read_loader_image(written)

        self.assertEqual(0, decoded["entry"])
        self.assertEqual([0, 0x10000], [segment["address"] for segment in decoded["segments"]])
        self.assertEqual(b"\x73\x00\x10\x00", decoded["segments"][0]["data"])
        self.assertEqual(b"\x78\x56\x34\x12", decoded["segments"][1]["data"])


if __name__ == "__main__":
    unittest.main()
