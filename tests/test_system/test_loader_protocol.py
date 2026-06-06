# UART loader paket protokolünün encode/decode, CRC32 doğrulama, hata yanıtı
# ve parçalı seri port okumalarında yeniden senkronizasyon davranışlarını test eder.

import unittest

from src.loader_protocol import (
    STATUS_BAD_CRC,
    TYPE_ACK,
    TYPE_DATA,
    ProtocolError,
    decode_packet,
    encode_packet,
    encode_response,
    read_packet,
)


class ByteStream:
    def __init__(self, data, chunk_size=None):
        self.data = bytearray(data)
        self.chunk_size = chunk_size

    def read(self, size):
        if not self.data:
            return b""
        if self.chunk_size:
            size = min(size, self.chunk_size)
        result = bytes(self.data[:size])
        del self.data[:size]
        return result


class LoaderProtocolTests(unittest.TestCase):
    def test_packet_round_trip_preserves_fields(self):
        encoded = encode_packet(TYPE_DATA, 7, address=0x100, payload=b"\x01\x02", flags=5)

        decoded = decode_packet(encoded)

        self.assertEqual(TYPE_DATA, decoded["type"])
        self.assertEqual(7, decoded["sequence"])
        self.assertEqual(0x100, decoded["address"])
        self.assertEqual(5, decoded["flags"])
        self.assertEqual(b"\x01\x02", decoded["payload"])

    def test_bad_packet_crc_is_rejected(self):
        encoded = bytearray(encode_packet(TYPE_DATA, 1, payload=b"test"))
        encoded[-1] ^= 0xFF

        with self.assertRaisesRegex(ProtocolError, "CRC32"):
            decode_packet(bytes(encoded))

    def test_read_packet_resynchronizes_and_handles_short_reads(self):
        packet = encode_response(12)
        decoded = read_packet(ByteStream(b"\x00\xFFgarbage" + packet, chunk_size=1))

        self.assertEqual(TYPE_ACK, decoded["type"])
        self.assertEqual(12, decoded["sequence"])

    def test_response_can_carry_error_status(self):
        decoded = decode_packet(encode_response(3, accepted=False, status=STATUS_BAD_CRC))

        self.assertEqual(bytes([STATUS_BAD_CRC]), decoded["payload"])


if __name__ == "__main__":
    unittest.main()
