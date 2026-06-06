import struct
import zlib


MAGIC = b"\xA5\x5A"
VERSION = 1
MAX_PAYLOAD = 128
HEADER = struct.Struct("<2sBBBBHI")
CRC32 = struct.Struct("<I")

TYPE_PING = 0x01
TYPE_BEGIN = 0x02
TYPE_DATA = 0x03
TYPE_END = 0x04
TYPE_RUN = 0x05
TYPE_ACK = 0x80
TYPE_NACK = 0x81

STATUS_OK = 0x00
STATUS_BAD_CRC = 0x01
STATUS_BAD_SEQUENCE = 0x02
STATUS_BAD_COMMAND = 0x03
STATUS_BAD_ADDRESS = 0x04
STATUS_BAD_LENGTH = 0x05
STATUS_NOT_READY = 0x06
STATUS_INTERNAL_ERROR = 0x07

BEGIN_PAYLOAD = struct.Struct("<IIHI")
END_PAYLOAD = struct.Struct("<II")


class ProtocolError(ValueError):
    pass


class ResponseError(ProtocolError):
    def __init__(self, sequence, status):
        super().__init__(f"NACK alındı: sequence={sequence}, status=0x{status:02X}")
        self.sequence = sequence
        self.status = status


def encode_packet(packet_type, sequence, address=0, payload=b"", flags=0):
    payload = bytes(payload)
    if len(payload) > MAX_PAYLOAD:
        raise ProtocolError(f"Payload en fazla {MAX_PAYLOAD} byte olabilir.")
    for value, label in (
        (packet_type, "Packet type"),
        (sequence, "Sequence"),
        (flags, "Flags"),
    ):
        if value < 0 or value > 0xFF:
            raise ProtocolError(f"{label} 8-bit unsigned aralık dışında: {value}")
    if address < 0 or address > 0xFFFFFFFF:
        raise ProtocolError(f"Address 32-bit unsigned aralık dışında: {address}")
    header = HEADER.pack(
        MAGIC,
        VERSION,
        packet_type,
        sequence,
        flags,
        len(payload),
        address,
    )
    packet_without_crc = header + payload
    return packet_without_crc + CRC32.pack(zlib.crc32(packet_without_crc) & 0xFFFFFFFF)


def decode_packet(packet):
    if len(packet) < HEADER.size + CRC32.size:
        raise ProtocolError("Paket başlığı veya CRC32 eksik.")
    magic, version, packet_type, sequence, flags, length, address = HEADER.unpack_from(packet)
    if magic != MAGIC:
        raise ProtocolError("Geçersiz paket magic değeri.")
    if version != VERSION:
        raise ProtocolError(f"Desteklenmeyen paket sürümü: {version}")
    if length > MAX_PAYLOAD:
        raise ProtocolError(f"Payload uzunluğu sınırı aşıyor: {length}")
    expected_size = HEADER.size + length + CRC32.size
    if len(packet) != expected_size:
        raise ProtocolError(f"Paket boyutu uyumsuz: beklenen={expected_size}, gerçek={len(packet)}")
    expected_crc = CRC32.unpack_from(packet, len(packet) - CRC32.size)[0]
    actual_crc = zlib.crc32(packet[:-CRC32.size]) & 0xFFFFFFFF
    if actual_crc != expected_crc:
        raise ProtocolError(
            f"Paket CRC32 hatası: beklenen=0x{expected_crc:08X}, gerçek=0x{actual_crc:08X}"
        )
    return {
        "type": packet_type,
        "sequence": sequence,
        "flags": flags,
        "address": address,
        "payload": packet[HEADER.size:-CRC32.size],
        "crc32": expected_crc,
    }


def read_packet(stream):
    magic = _read_magic(stream)
    rest = _read_exact(stream, HEADER.size - len(MAGIC))
    header = magic + rest
    _, version, _, _, _, length, _ = HEADER.unpack(header)
    if version != VERSION:
        raise ProtocolError(f"Desteklenmeyen paket sürümü: {version}")
    if length > MAX_PAYLOAD:
        raise ProtocolError(f"Payload uzunluğu sınırı aşıyor: {length}")
    return decode_packet(header + _read_exact(stream, length + CRC32.size))


def encode_response(sequence, accepted=True, status=STATUS_OK):
    packet_type = TYPE_ACK if accepted else TYPE_NACK
    return encode_packet(packet_type, sequence, payload=bytes([status]))


def _read_magic(stream):
    matched = bytearray()
    while len(matched) < len(MAGIC):
        byte = stream.read(1)
        if not byte:
            raise TimeoutError("UART yanıtı beklenirken timeout oluştu.")
        if byte == MAGIC[len(matched):len(matched) + 1]:
            matched.extend(byte)
        else:
            matched = bytearray(byte if byte == MAGIC[:1] else b"")
    return bytes(matched)


def _read_exact(stream, size):
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            raise TimeoutError("UART paketi tamamlanmadan timeout oluştu.")
        data.extend(chunk)
    return bytes(data)
