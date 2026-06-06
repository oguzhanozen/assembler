import argparse
import os
import struct
import sys
import zlib


MAGIC = b"PICOIMG\x00"
VERSION = 1
HEADER = struct.Struct("<8sHHIIIII")
SEGMENT = struct.Struct("<IIII")

FLAG_READ = 1 << 0
FLAG_WRITE = 1 << 1
FLAG_EXECUTE = 1 << 2


class LoaderImageError(ValueError):
    pass


def region_flags_to_bits(flags):
    bits = 0
    if "r" in flags:
        bits |= FLAG_READ
    if "w" in flags:
        bits |= FLAG_WRITE
    if "x" in flags:
        bits |= FLAG_EXECUTE
    return bits


def bits_to_region_flags(bits):
    return "".join(
        flag
        for flag, mask in (("r", FLAG_READ), ("w", FLAG_WRITE), ("x", FLAG_EXECUTE))
        if bits & mask
    )


def linked_object_to_segments(linked_object):
    segments = []
    for region in linked_object.get("memory_regions", []):
        words = region.get("memory_words", [])
        if not words:
            continue
        data = bytearray()
        for index, word in enumerate(words):
            try:
                value = int(str(word), 16)
            except (TypeError, ValueError) as exc:
                raise LoaderImageError(
                    f"Memory region '{region.get('name')}' geçersiz word #{index}: {word}"
                ) from exc
            if value < 0 or value > 0xFFFFFFFF:
                raise LoaderImageError(
                    f"Memory region '{region.get('name')}' 32-bit dışında word içeriyor: {word}"
                )
            data.extend(value.to_bytes(4, "little"))
        segments.append(
            {
                "address": int(region["origin"]),
                "flags": region_flags_to_bits(region.get("flags", "")),
                "data": bytes(data),
            }
        )
    return segments


def encode_loader_image(entry, segments):
    entry = _uint32(entry, "Entry adresi")
    normalized = _normalize_segments(segments)
    descriptors = bytearray()
    payload = bytearray()
    for segment in normalized:
        data = segment["data"]
        descriptors.extend(
            SEGMENT.pack(
                segment["address"],
                len(data),
                segment["flags"],
                zlib.crc32(data) & 0xFFFFFFFF,
            )
        )
        payload.extend(data)
    body = bytes(descriptors + payload)
    header = HEADER.pack(
        MAGIC,
        VERSION,
        HEADER.size,
        entry,
        len(normalized),
        SEGMENT.size,
        len(payload),
        zlib.crc32(body) & 0xFFFFFFFF,
    )
    return header + body


def encode_linked_object(linked_object):
    try:
        entry = linked_object["entry"]
    except KeyError as exc:
        raise LoaderImageError("Linked object entry adresi içermiyor.") from exc
    return encode_loader_image(entry, linked_object_to_segments(linked_object))


def decode_loader_image(image):
    if len(image) < HEADER.size:
        raise LoaderImageError("Loader image başlığı eksik.")
    (
        magic,
        version,
        header_size,
        entry,
        segment_count,
        descriptor_size,
        payload_size,
        image_crc32,
    ) = HEADER.unpack_from(image)
    if magic != MAGIC:
        raise LoaderImageError("Geçersiz loader image magic değeri.")
    if version != VERSION:
        raise LoaderImageError(f"Desteklenmeyen loader image sürümü: {version}")
    if header_size != HEADER.size or descriptor_size != SEGMENT.size:
        raise LoaderImageError("Loader image başlık veya segment boyutu uyumsuz.")

    descriptor_bytes = segment_count * descriptor_size
    expected_size = header_size + descriptor_bytes + payload_size
    if len(image) != expected_size:
        raise LoaderImageError(
            f"Loader image boyutu uyumsuz: beklenen={expected_size}, gerçek={len(image)}"
        )
    body = image[header_size:]
    actual_image_crc32 = zlib.crc32(body) & 0xFFFFFFFF
    if actual_image_crc32 != image_crc32:
        raise LoaderImageError(
            f"Loader image CRC32 hatası: beklenen=0x{image_crc32:08X}, gerçek=0x{actual_image_crc32:08X}"
        )

    payload_offset = header_size + descriptor_bytes
    cursor = payload_offset
    segments = []
    for index in range(segment_count):
        address, length, flags, data_crc32 = SEGMENT.unpack_from(
            image, header_size + index * descriptor_size
        )
        data = image[cursor:cursor + length]
        if len(data) != length:
            raise LoaderImageError(f"Segment #{index} verisi eksik.")
        actual_data_crc32 = zlib.crc32(data) & 0xFFFFFFFF
        if actual_data_crc32 != data_crc32:
            raise LoaderImageError(
                f"Segment #{index} CRC32 hatası: beklenen=0x{data_crc32:08X}, "
                f"gerçek=0x{actual_data_crc32:08X}"
            )
        segments.append(
            {
                "address": address,
                "length": length,
                "flags": flags,
                "data_crc32": data_crc32,
                "data": data,
            }
        )
        cursor += length
    if cursor != len(image):
        raise LoaderImageError(
            f"Segment uzunlukları payload boyutuyla eşleşmiyor: "
            f"beklenen={payload_size}, kullanılan={cursor - payload_offset}"
        )
    _validate_segment_ranges(segments)
    return {
        "format": "picorv-loader-image",
        "version": version,
        "entry": entry,
        "image_crc32": image_crc32,
        "segments": segments,
    }


def write_loader_image(linked_object, path):
    image = encode_linked_object(linked_object)
    output_dir = os.path.dirname(os.path.abspath(path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(path, "wb") as output:
        output.write(image)
    return os.path.abspath(path)


def read_loader_image(path):
    try:
        with open(path, "rb") as source:
            return decode_loader_image(source.read())
    except OSError as exc:
        raise LoaderImageError(f"Loader image okunamadı: {exc}") from exc


def _uint32(value, label):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise LoaderImageError(f"{label} sayı olmalı: {value}") from exc
    if parsed < 0 or parsed > 0xFFFFFFFF:
        raise LoaderImageError(f"{label} 32-bit unsigned aralık dışında: {parsed}")
    return parsed


def _normalize_segments(segments):
    normalized = []
    for index, segment in enumerate(segments):
        try:
            data = bytes(segment["data"])
            address = _uint32(segment["address"], f"Segment #{index} adresi")
            flags = _uint32(segment.get("flags", 0), f"Segment #{index} flags")
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, LoaderImageError):
                raise
            raise LoaderImageError(f"Segment #{index} geçersiz: {exc}") from exc
        if not data:
            raise LoaderImageError(f"Segment #{index} boş olamaz.")
        if address + len(data) > 0x100000000:
            raise LoaderImageError(f"Segment #{index} 32-bit adres alanını aşıyor.")
        normalized.append({"address": address, "flags": flags, "data": data})
    _validate_segment_ranges(normalized)
    return normalized


def _validate_segment_ranges(segments):
    ranges = sorted(
        (segment["address"], segment["address"] + len(segment["data"]), index)
        for index, segment in enumerate(segments)
    )
    for previous, current in zip(ranges, ranges[1:]):
        if current[0] < previous[1]:
            raise LoaderImageError(
                f"Loader image segmentleri çakışıyor: #{previous[2]} ve #{current[2]}"
            )


def main(argv=None):
    parser = argparse.ArgumentParser(description="PicoRV loader image doğrulayıcı")
    parser.add_argument("image", help="İncelenecek .picoimg dosyası")
    args = parser.parse_args(argv)
    try:
        decoded = read_loader_image(args.image)
    except LoaderImageError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Format: {decoded['format']} v{decoded['version']}")
    print(f"Entry: 0x{decoded['entry']:08X}")
    print(f"Image CRC32: 0x{decoded['image_crc32']:08X}")
    for index, segment in enumerate(decoded["segments"]):
        print(
            f"Segment #{index}: address=0x{segment['address']:08X} "
            f"length={segment['length']} flags={bits_to_region_flags(segment['flags'])} "
            f"crc32=0x{segment['data_crc32']:08X}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
