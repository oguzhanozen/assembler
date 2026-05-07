import argparse
import json
import os
import sys


def align_up(value, alignment):
    return (value + alignment - 1) // alignment * alignment


def to_hex_word(value):
    return f"0x{value & 0xFFFFFFFF:08X}"


class PicoRVLinker:
    def __init__(self, text_base=0x00000000):
        self.text_base = text_base
        self.errors = []

    def link(self, object_paths):
        self.errors = []
        objects = self.load_objects(object_paths)
        if self.errors:
            return None, self.errors

        self.assign_layout(objects)
        global_symbols = self.build_global_symbols(objects)
        self.validate_extern_symbols(objects, global_symbols)
        if self.errors:
            return None, self.errors

        final_text = self.collect_text(objects)
        final_data_bytes = self.collect_data_bytes(objects)
        applied_relocations = self.apply_relocations(objects, final_text, global_symbols)
        if self.errors:
            return None, self.errors

        data_words = self.pack_data_words(final_data_bytes)
        memory_words = [to_hex_word(word) for word in final_text] + data_words
        linked_object = {
            "entry": global_symbols.get("main", {}).get("address", self.text_base),
            "layout": {
                "text_base": self.text_base,
                "data_base": objects[0]["layout"]["data_segment_base"] if objects else align_up(self.text_base, 4),
                "objects": [
                    {
                        "path": obj["path"],
                        "name": obj["name"],
                        "text_base": obj["layout"]["text_base"],
                        "text_size": obj["layout"]["text_size"],
                        "data_base": obj["layout"]["data_base"],
                        "data_size": obj["layout"]["data_size"],
                    }
                    for obj in objects
                ],
            },
            "text": [to_hex_word(word) for word in final_text],
            "data_bytes": [f"0x{byte:02X}" for byte in final_data_bytes],
            "data_words": data_words,
            "memory_words": memory_words,
            "symbols": global_symbols,
            "applied_relocations": applied_relocations,
        }
        return linked_object, []

    def load_objects(self, object_paths):
        objects = []
        for index, path in enumerate(object_paths):
            try:
                with open(path, "r", encoding="utf-8") as obj_file:
                    data = json.load(obj_file)
            except (OSError, json.JSONDecodeError) as exc:
                self.errors.append(f"{path}: object dosyası okunamadı: {exc}")
                continue

            missing = [key for key in ("text", "data", "symbols", "relocations") if key not in data]
            if missing:
                self.errors.append(f"{path}: eksik object alanları: {', '.join(missing)}")
                continue

            objects.append(
                {
                    "index": index,
                    "path": os.path.abspath(path),
                    "name": os.path.basename(path),
                    "raw": data,
                    "data_bytes": self.data_entries_to_bytes(data.get("data", []), path),
                    "layout": {},
                }
            )
        return objects

    def assign_layout(self, objects):
        text_cursor = self.text_base
        for obj in objects:
            text_size = len(obj["raw"]["text"]) * 4
            obj["layout"]["text_base"] = text_cursor
            obj["layout"]["text_size"] = text_size
            text_cursor += text_size

        data_cursor = align_up(text_cursor, 4)
        data_segment_base = data_cursor
        for obj in objects:
            data_size = len(obj["data_bytes"])
            obj["layout"]["data_segment_base"] = data_segment_base
            obj["layout"]["data_base"] = data_cursor
            obj["layout"]["data_size"] = data_size
            data_cursor += data_size

    def build_global_symbols(self, objects):
        global_symbols = {}
        for obj in objects:
            for name, info in obj["raw"]["symbols"].items():
                if info.get("visibility") != "global" or info.get("section") == "UNDEF":
                    continue

                if name in global_symbols:
                    previous = global_symbols[name]["object"]
                    self.errors.append(f"Duplicate global symbol '{name}': {previous} ve {obj['name']}")
                    continue

                global_symbols[name] = self.symbol_record(obj, name, info)
        return global_symbols

    def validate_extern_symbols(self, objects, global_symbols):
        for obj in objects:
            for name, info in obj["raw"]["symbols"].items():
                if info.get("visibility") == "extern" and name not in global_symbols:
                    self.errors.append(f"Unresolved extern symbol '{name}' in {obj['name']}")

    def collect_text(self, objects):
        final_text = []
        for obj in objects:
            for offset, text_word in enumerate(obj["raw"]["text"]):
                try:
                    final_text.append(int(text_word, 16))
                except (TypeError, ValueError):
                    self.errors.append(f"{obj['name']}: geçersiz text word #{offset}: {text_word}")
                    final_text.append(0)
        return final_text

    def collect_data_bytes(self, objects):
        final_data = []
        for obj in objects:
            final_data.extend(obj["data_bytes"])
        return final_data

    def apply_relocations(self, objects, final_text, global_symbols):
        applied = []
        for obj in objects:
            for relocation in obj["raw"]["relocations"]:
                result = self.apply_relocation(obj, relocation, final_text, global_symbols)
                if result:
                    applied.append(result)
        return applied

    def apply_relocation(self, obj, relocation, final_text, global_symbols):
        if relocation.get("section") != ".text":
            self.errors.append(f"{obj['name']}: desteklenmeyen relocation section: {relocation.get('section')}")
            return None

        try:
            offset = int(relocation["offset"])
        except (KeyError, TypeError, ValueError):
            self.errors.append(f"{obj['name']}: geçersiz relocation offset: {relocation}")
            return None

        if offset % 4 != 0 or offset < 0 or offset >= obj["layout"]["text_size"]:
            self.errors.append(f"{obj['name']}: relocation text offset aralık dışında: {offset}")
            return None

        symbol_name = relocation.get("symbol")
        symbol = self.resolve_symbol(obj, symbol_name, global_symbols)
        if not symbol:
            self.errors.append(f"Unresolved symbol '{symbol_name}' referenced by {obj['name']} offset 0x{offset:X}")
            return None

        word_index = (obj["layout"]["text_base"] - self.text_base + offset) // 4
        original_word = final_text[word_index]
        patch_address = obj["layout"]["text_base"] + offset
        relocation_type = relocation.get("type")

        try:
            patched_word = self.patch_word(original_word, relocation_type, symbol["address"], patch_address)
        except ValueError as exc:
            self.errors.append(f"{obj['name']} offset 0x{offset:X}: {exc}")
            return None

        final_text[word_index] = patched_word
        return {
            "object": obj["name"],
            "offset": offset,
            "patch_address": patch_address,
            "type": relocation_type,
            "symbol": symbol_name,
            "target_address": symbol["address"],
            "original": to_hex_word(original_word),
            "patched": to_hex_word(patched_word),
        }

    def resolve_symbol(self, obj, symbol_name, global_symbols):
        local_info = obj["raw"]["symbols"].get(symbol_name)
        if local_info and local_info.get("section") != "UNDEF":
            return self.symbol_record(obj, symbol_name, local_info)
        return global_symbols.get(symbol_name)

    def symbol_record(self, obj, name, info):
        section = info.get("section")
        if section == ".text":
            address = obj["layout"]["text_base"] + int(info.get("offset", 0))
        elif section == ".data":
            address = obj["layout"]["data_base"] + int(info.get("offset", 0))
        else:
            address = int(info.get("offset", 0))

        return {
            "address": address,
            "section": section,
            "offset": int(info.get("offset", 0)),
            "visibility": info.get("visibility", "local"),
            "object": obj["name"],
        }

    def patch_word(self, word, relocation_type, target_address, patch_address):
        if relocation_type == "R_RISCV_HI20":
            return self.patch_hi20(word, target_address, patch_address)
        if relocation_type == "R_RISCV_LO12_I":
            return self.patch_lo12_i(word, target_address)
        if relocation_type == "R_RISCV_LO12_S":
            return self.patch_lo12_s(word, target_address)
        if relocation_type == "R_RISCV_BRANCH":
            return self.patch_branch(word, target_address - patch_address)
        if relocation_type == "R_RISCV_JAL":
            return self.patch_jal(word, target_address - patch_address)
        raise ValueError(f"desteklenmeyen relocation tipi: {relocation_type}")

    def patch_hi20(self, word, target_address, patch_address):
        opcode = word & 0x7F
        if opcode == 0x17:
            value = target_address - patch_address
        elif opcode == 0x37:
            value = target_address
        else:
            raise ValueError("R_RISCV_HI20 sadece auipc veya lui üzerinde uygulanabilir")

        imm20 = ((value + 0x800) >> 12) & 0xFFFFF
        return (word & 0x00000FFF) | (imm20 << 12)

    def patch_lo12_i(self, word, target_address):
        imm12 = target_address & 0xFFF
        return (word & 0x000FFFFF) | (imm12 << 20)

    def patch_lo12_s(self, word, target_address):
        imm12 = target_address & 0xFFF
        word &= ~((0x7F << 25) | (0x1F << 7)) & 0xFFFFFFFF
        return word | (((imm12 >> 5) & 0x7F) << 25) | ((imm12 & 0x1F) << 7)

    def patch_branch(self, word, offset):
        if offset % 2 != 0 or offset < -4096 or offset > 4094:
            raise ValueError(f"branch hedef offset'i 13-bit hizalı aralık dışında: {offset}")

        imm = offset & 0x1FFF
        word &= ~((1 << 31) | (0x3F << 25) | (0xF << 8) | (1 << 7)) & 0xFFFFFFFF
        return (
            word
            | (((imm >> 12) & 0x1) << 31)
            | (((imm >> 5) & 0x3F) << 25)
            | (((imm >> 1) & 0xF) << 8)
            | (((imm >> 11) & 0x1) << 7)
        )

    def patch_jal(self, word, offset):
        if offset % 2 != 0 or offset < -1048576 or offset > 1048574:
            raise ValueError(f"jal hedef offset'i 21-bit hizalı aralık dışında: {offset}")

        imm = offset & 0x1FFFFF
        word &= 0x00000FFF
        return (
            word
            | (((imm >> 20) & 0x1) << 31)
            | (((imm >> 1) & 0x3FF) << 21)
            | (((imm >> 11) & 0x1) << 20)
            | (((imm >> 12) & 0xFF) << 12)
        )

    def data_entries_to_bytes(self, data_entries, path):
        data_bytes = []
        for index, entry in enumerate(data_entries):
            try:
                hex_part = str(entry).strip()
                if not hex_part.lower().startswith("0x"):
                    raise ValueError("0x ile başlamalı")
                digits = hex_part[2:]
                if len(digits) == 2:
                    data_bytes.append(int(digits, 16) & 0xFF)
                elif len(digits) == 8:
                    value = int(digits, 16)
                    data_bytes.extend((value >> shift) & 0xFF for shift in (0, 8, 16, 24))
                else:
                    raise ValueError("yalnızca 1-byte veya 4-byte veri desteklenir")
            except ValueError as exc:
                self.errors.append(f"{path}: geçersiz data entry #{index}: {entry} ({exc})")
        return data_bytes

    def pack_data_words(self, data_bytes):
        words = []
        for start in range(0, len(data_bytes), 4):
            chunk = data_bytes[start:start + 4]
            while len(chunk) < 4:
                chunk.append(0)
            value = chunk[0] | (chunk[1] << 8) | (chunk[2] << 16) | (chunk[3] << 24)
            words.append(to_hex_word(value))
        return words

    def write_outputs(self, linked_object, output_prefix):
        output_dir = os.path.dirname(os.path.abspath(output_prefix))
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        json_path = f"{output_prefix}.linked.json"
        hex_path = f"{output_prefix}.hex"
        with open(json_path, "w", encoding="utf-8") as json_file:
            json.dump(linked_object, json_file, indent=4)
        with open(hex_path, "w", encoding="utf-8") as hex_file:
            for word in linked_object["memory_words"]:
                hex_file.write(f"{word[2:]}\n")
        return {"json": os.path.abspath(json_path), "hex": os.path.abspath(hex_path)}


def build_arg_parser():
    parser = argparse.ArgumentParser(description="PicoRV JSON object linker")
    parser.add_argument("objects", nargs="+", help="Linklenecek .o JSON object dosyaları")
    parser.add_argument("-o", "--output", default=os.path.join("outputs", "program"), help="Çıktı prefix'i")
    parser.add_argument("--text-base", default="0x0", help="Text başlangıç adresi")
    return parser


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        text_base = int(args.text_base, 0)
    except ValueError:
        print(f"Geçersiz --text-base değeri: {args.text_base}", file=sys.stderr)
        return 2

    linker = PicoRVLinker(text_base=text_base)
    linked_object, errors = linker.link(args.objects)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    paths = linker.write_outputs(linked_object, args.output)
    print(f"Linked JSON: {paths['json']}")
    print(f"HEX: {paths['hex']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
