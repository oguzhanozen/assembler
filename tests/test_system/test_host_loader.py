# UART host loader'ın paket sıralamasını, image aktarımını, ACK/NACK yanıtlarını
# ve timeout durumunda aynı paketi sequence değiştirmeden yeniden göndermesini test eder.

import unittest
import zlib

from src.host_loader import HostLoader, HostLoaderError
from src.loader_protocol import (
    BEGIN_PAYLOAD,
    END_PAYLOAD,
    STATUS_BAD_CRC,
    TYPE_BEGIN,
    TYPE_DATA,
    TYPE_END,
    TYPE_RUN,
    decode_packet,
    encode_response,
)


class FakeSerial:
    def __init__(self, actions=None):
        self.actions = list(actions or [])
        self.responses = bytearray()
        self.writes = []

    def write(self, data):
        packet = decode_packet(data)
        self.writes.append(packet)
        action = self.actions.pop(0) if self.actions else "ack"
        if action == "timeout":
            return len(data)
        if action == "nack":
            self.responses.extend(
                encode_response(packet["sequence"], accepted=False, status=STATUS_BAD_CRC)
            )
        else:
            self.responses.extend(encode_response(packet["sequence"]))
        return len(data)

    def read(self, size):
        if not self.responses:
            return b""
        result = bytes(self.responses[:size])
        del self.responses[:size]
        return result

    def flush(self):
        pass


class HostLoaderTests(unittest.TestCase):
    def image(self, data=b"A" * 140):
        return {
            "entry": 0x20,
            "image_crc32": 0x12345678,
            "segments": [
                {
                    "address": 0x20,
                    "flags": 5,
                    "data": data,
                }
            ],
        }

    def test_load_image_sends_begin_chunked_data_end_and_run(self):
        serial = FakeSerial()
        progress = []
        loader = HostLoader(serial, retry_delay=0, progress=lambda sent, total: progress.append((sent, total)))

        result = loader.load_image(self.image())

        self.assertEqual([TYPE_BEGIN, TYPE_DATA, TYPE_DATA, TYPE_END, TYPE_RUN], [p["type"] for p in serial.writes])
        self.assertEqual([0, 1, 2, 3, 4], [p["sequence"] for p in serial.writes])
        self.assertEqual([0x20, 0xA0], [p["address"] for p in serial.writes if p["type"] == TYPE_DATA])
        self.assertEqual([128, 12], [len(p["payload"]) for p in serial.writes if p["type"] == TYPE_DATA])
        transfer_crc = zlib.crc32(b"A" * 140) & 0xFFFFFFFF
        self.assertEqual((0x20, 140, 1, transfer_crc), BEGIN_PAYLOAD.unpack(serial.writes[0]["payload"]))
        self.assertEqual((140, transfer_crc), END_PAYLOAD.unpack(serial.writes[-2]["payload"]))
        self.assertEqual([(128, 140), (140, 140)], progress)
        self.assertEqual({"bytes_sent": 140, "segments": 1, "entry": 0x20}, result)

    def test_timeout_retries_identical_packet_without_advancing_sequence(self):
        serial = FakeSerial(["timeout", "ack"])
        loader = HostLoader(serial, retries=2, retry_delay=0)

        loader.ping()

        self.assertEqual(2, len(serial.writes))
        self.assertEqual([0, 0], [packet["sequence"] for packet in serial.writes])
        self.assertEqual(1, loader.sequence)

    def test_nack_is_retried(self):
        serial = FakeSerial(["nack", "ack"])
        loader = HostLoader(serial, retries=2, retry_delay=0)

        loader.ping()

        self.assertEqual(2, len(serial.writes))
        self.assertEqual(1, loader.sequence)

    def test_retry_exhaustion_raises_host_loader_error(self):
        serial = FakeSerial(["timeout", "timeout"])
        loader = HostLoader(serial, retries=2, retry_delay=0)

        with self.assertRaises(HostLoaderError):
            loader.ping()


if __name__ == "__main__":
    unittest.main()
