import argparse
import sys
import time
import zlib

from src.loader_image import LoaderImageError, read_loader_image
from src.loader_protocol import (
    BEGIN_PAYLOAD,
    END_PAYLOAD,
    MAX_PAYLOAD,
    STATUS_OK,
    TYPE_ACK,
    TYPE_BEGIN,
    TYPE_DATA,
    TYPE_END,
    TYPE_NACK,
    TYPE_PING,
    TYPE_RUN,
    ProtocolError,
    ResponseError,
    encode_packet,
    read_packet,
)


class HostLoaderError(RuntimeError):
    pass


TARGET_ENTRY_ADDRESS = 0x00000000


def validate_target_image(image):
    entry = image["entry"]
    if entry != TARGET_ENTRY_ADDRESS:
        raise HostLoaderError(
            f"Mevcut FPGA hedefi yalnızca entry=0x{TARGET_ENTRY_ADDRESS:08X} destekliyor; "
            f"image entry=0x{entry:08X}. Link aşamasında _start içeren ana object dosyasını "
            "ilk sıraya yerleştirin."
        )


class HostLoader:
    def __init__(self, stream, retries=3, retry_delay=0.05, progress=None):
        if retries < 1:
            raise ValueError("retries en az 1 olmalı.")
        self.stream = stream
        self.retries = retries
        self.retry_delay = retry_delay
        self.progress = progress
        self.sequence = 0

    def ping(self):
        self._transact(TYPE_PING)

    def load_image(self, image):
        validate_target_image(image)
        segments = image["segments"]
        total_bytes = sum(len(segment["data"]) for segment in segments)
        transfer_crc32 = 0
        for segment in segments:
            transfer_crc32 = zlib.crc32(segment["data"], transfer_crc32)
        transfer_crc32 &= 0xFFFFFFFF
        begin_payload = BEGIN_PAYLOAD.pack(
            image["entry"],
            total_bytes,
            len(segments),
            transfer_crc32,
        )
        self._transact(TYPE_BEGIN, payload=begin_payload)

        sent = 0
        for segment in segments:
            data = segment["data"]
            for offset in range(0, len(data), MAX_PAYLOAD):
                chunk = data[offset:offset + MAX_PAYLOAD]
                self._transact(
                    TYPE_DATA,
                    address=segment["address"] + offset,
                    payload=chunk,
                    flags=segment["flags"] & 0xFF,
                )
                sent += len(chunk)
                if self.progress:
                    self.progress(sent, total_bytes)

        self._transact(
            TYPE_END,
            payload=END_PAYLOAD.pack(total_bytes, transfer_crc32),
        )
        self._transact(TYPE_RUN, address=image["entry"])
        return {"bytes_sent": sent, "segments": len(segments), "entry": image["entry"]}

    def _transact(self, packet_type, address=0, payload=b"", flags=0):
        sequence = self.sequence
        packet = encode_packet(packet_type, sequence, address, payload, flags)
        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                self.stream.write(packet)
                if hasattr(self.stream, "flush"):
                    self.stream.flush()
                response = read_packet(self.stream)
                self._validate_response(response, sequence)
                self.sequence = (self.sequence + 1) & 0xFF
                return
            except (TimeoutError, ProtocolError, OSError) as exc:
                last_error = exc
                if attempt < self.retries and self.retry_delay:
                    time.sleep(self.retry_delay)
        raise HostLoaderError(
            f"Paket {self.retries} denemede gönderilemedi "
            f"(type=0x{packet_type:02X}, sequence={sequence}): {last_error}"
        ) from last_error

    def _validate_response(self, response, sequence):
        if response["sequence"] != sequence:
            raise ProtocolError(
                f"Yanıt sequence uyuşmuyor: beklenen={sequence}, gelen={response['sequence']}"
            )
        status = response["payload"][0] if response["payload"] else STATUS_OK
        if response["type"] == TYPE_NACK:
            raise ResponseError(sequence, status)
        if response["type"] != TYPE_ACK:
            raise ProtocolError(f"ACK/NACK yerine beklenmeyen paket alındı: 0x{response['type']:02X}")
        if status != STATUS_OK:
            raise ProtocolError(f"ACK hata status değeri içeriyor: 0x{status:02X}")


def open_serial(port, baudrate, timeout):
    try:
        import serial
    except ImportError as exc:
        raise HostLoaderError(
            "UART yükleme için pyserial kurulu değil. 'python -m pip install pyserial' çalıştırın."
        ) from exc
    try:
        return serial.Serial(port=port, baudrate=baudrate, timeout=timeout, write_timeout=timeout)
    except serial.SerialException as exc:
        raise HostLoaderError(f"Seri port açılamadı: {exc}") from exc


def list_serial_ports():
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise HostLoaderError(
            "Port listelemek için pyserial kurulu değil. 'python -m pip install pyserial' çalıştırın."
        ) from exc
    return list(list_ports.comports())


def build_arg_parser():
    parser = argparse.ArgumentParser(description="PicoRV UART host loader")
    parser.add_argument("image", nargs="?", help="Gönderilecek .picoimg dosyası")
    parser.add_argument("--port", help="Seri port adı, örn. COM5")
    parser.add_argument("--baud", type=int, default=115200, help="UART baud rate")
    parser.add_argument("--timeout", type=float, default=1.0, help="Paket yanıt timeout süresi")
    parser.add_argument("--retries", type=int, default=3, help="Her paket için gönderme denemesi")
    parser.add_argument("--list-ports", action="store_true", help="Kullanılabilir seri portları listele")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Image ve oluşturulacak paketleri doğrula, seri porta gönderme",
    )
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    try:
        if args.list_ports:
            for port in list_serial_ports():
                print(f"{port.device}: {port.description}")
            return 0
        if not args.image:
            raise HostLoaderError(".picoimg dosyası belirtilmeli.")
        image = read_loader_image(args.image)
        validate_target_image(image)
        total_bytes = sum(len(segment["data"]) for segment in image["segments"])
        if args.dry_run:
            packet_count = 3 + sum(
                (len(segment["data"]) + MAX_PAYLOAD - 1) // MAX_PAYLOAD
                for segment in image["segments"]
            )
            print(
                f"Image geçerli: entry=0x{image['entry']:08X}, "
                f"segments={len(image['segments'])}, bytes={total_bytes}, packets={packet_count}"
            )
            return 0
        if not args.port:
            raise HostLoaderError("--port belirtilmeli.")

        def show_progress(sent, total):
            print(f"\rGönderiliyor: {sent}/{total} byte", end="", flush=True)

        with open_serial(args.port, args.baud, args.timeout) as stream:
            loader = HostLoader(stream, retries=args.retries, progress=show_progress)
            loader.ping()
            result = loader.load_image(image)
        print(
            f"\nYükleme tamamlandı: {result['bytes_sent']} byte, "
            f"{result['segments']} segment, entry=0x{result['entry']:08X}"
        )
        return 0
    except (HostLoaderError, LoaderImageError, ProtocolError, OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
