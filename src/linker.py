import argparse
import fnmatch
import json
import os
import sys

from src.loader_image import write_loader_image
from src.project_paths import LINKER_OUTPUT_DIR, LOADER_OUTPUT_DIR, ensure_output_dirs
from src.linker_script import (
    InputSelector,
    LinkerScriptError,
    LocationAssignment,
    evaluate_expression,
    parse_linker_script,
)


def align_up(value, alignment):
    return (value + alignment - 1) // alignment * alignment


def to_hex_word(value):
    return f"0x{value & 0xFFFFFFFF:08X}"


class PicoRVLinker:
    def __init__(self, script_path=None):
        self.script_path = script_path
        self.errors = []
        self.regions = {}

    def link(self, object_paths, script_path=None):
        self.errors = []
        selected_script = script_path or self.script_path
        if not selected_script:
            return None, ["Linker script zorunludur. -T/--script ile bir .ld dosyası belirtin."]

        script = self.load_script(selected_script)
        objects = self.load_objects(object_paths)
        if self.errors:
            return None, self.errors

        self.regions = self.build_regions(script)
        output_sections = self.place_sections(objects, script)
        if self.errors:
            return None, self.errors

        global_symbols = self.build_global_symbols(objects)
        self.validate_extern_symbols(objects, global_symbols)
        entry_symbol = global_symbols.get(script.entry)
        if not entry_symbol:
            self.errors.append(f"ENTRY sembolü '{script.entry}' tanımlı global sembol değil.")
        if self.errors:
            return None, self.errors

        applied_relocations = self.apply_relocations(objects, global_symbols)
        if self.errors:
            return None, self.errors

        region_images = self.build_region_images(objects)
        if self.errors:
            return None, self.errors

        linked_object = {
            "format": "picorv-linked-image",
            "version": 2,
            "script": os.path.abspath(selected_script),
            "entry_symbol": script.entry,
            "entry": entry_symbol["address"],
            "memory_regions": [
                {
                    "name": region["name"],
                    "flags": region["flags"],
                    "origin": region["origin"],
                    "length": region["length"],
                    "used": region["cursor"] - region["origin"],
                    "memory_words": region_images[region["name"]]["memory_words"],
                }
                for region in self.regions.values()
            ],
            "output_sections": output_sections,
            "object_sections": [
                {
                    "object": obj["name"],
                    "section": section["name"],
                    "type": section["type"],
                    "flags": section["flags"],
                    "alignment": section["alignment"],
                    "size": section["size"],
                    "address": section["layout"]["address"],
                    "output_section": section["layout"]["output_section"],
                    "region": section["layout"]["region"],
                    "noload": section["layout"]["noload"],
                }
                for obj in objects
                for section in obj["sections"]
            ],
            "symbols": global_symbols,
            "applied_relocations": applied_relocations,
        }
        return linked_object, []

    def load_script(self, path):
        try:
            with open(path, "r", encoding="utf-8-sig") as script_file:
                return parse_linker_script(script_file.read())
        except (OSError, LinkerScriptError) as exc:
            self.errors.append(f"{path}: linker script okunamadı: {exc}")
            return None

    def build_regions(self, script):
        if not script:
            return {}
        regions = {}
        for definition in script.memory:
            if definition.name in regions:
                self.errors.append(f"Duplicate memory region: '{definition.name}'")
                continue
            try:
                origin = evaluate_expression(definition.origin_expr, regions=regions)
                length = evaluate_expression(definition.length_expr, regions=regions)
            except LinkerScriptError as exc:
                self.errors.append(f"Memory region '{definition.name}': {exc}")
                continue
            if origin < 0 or length <= 0:
                self.errors.append(f"Memory region '{definition.name}' origin >= 0 ve length > 0 olmalı.")
                continue
            if origin % 4:
                self.errors.append(f"Memory region '{definition.name}' origin adresi 4-byte hizalı olmalı.")
            region = {
                "name": definition.name,
                "flags": definition.flags,
                "origin": origin,
                "length": length,
                "cursor": origin,
            }
            for previous in regions.values():
                if origin < previous["origin"] + previous["length"] and previous["origin"] < origin + length:
                    self.errors.append(
                        f"Memory region çakışması: '{definition.name}' ve '{previous['name']}'"
                    )
            regions[definition.name] = region
        return regions

    def load_objects(self, object_paths):
        objects = []
        for index, path in enumerate(object_paths):
            try:
                with open(path, "r", encoding="utf-8-sig") as obj_file:
                    raw = json.load(obj_file)
            except (OSError, json.JSONDecodeError) as exc:
                self.errors.append(f"{path}: object dosyası okunamadı: {exc}")
                continue
            try:
                normalized = self.normalize_object(raw, path, index)
            except ValueError as exc:
                self.errors.append(f"{path}: {exc}")
                continue
            objects.append(normalized)
        return objects

    def normalize_object(self, raw, path, index):
        if raw.get("version") == 2 and raw.get("format") == "picorv-json-object":
            sections = []
            for section_index, section in enumerate(raw.get("sections", [])):
                sections.append(self.normalize_section(section, section_index))
        elif all(key in raw for key in ("text", "data", "symbols", "relocations")):
            sections = self.convert_v1_sections(raw, path)
        else:
            raise ValueError("desteklenmeyen veya eksik object formatı")

        section_names = {section["name"] for section in sections}
        if len(section_names) != len(sections):
            raise ValueError("duplicate section adı")
        for name, info in raw.get("symbols", {}).items():
            if info.get("section") not in section_names and info.get("section") != "UNDEF":
                raise ValueError(f"sembol '{name}' bilinmeyen section kullanıyor: {info.get('section')}")
            if info.get("section") in section_names:
                section = next(item for item in sections if item["name"] == info.get("section"))
                offset = int(info.get("offset", 0))
                if offset < 0 or offset > section["size"]:
                    raise ValueError(f"sembol '{name}' section sınırları dışında: {offset}")
        return {
            "index": index,
            "path": os.path.abspath(path),
            "name": os.path.basename(path),
            "symbols": raw.get("symbols", {}),
            "relocations": raw.get("relocations", []),
            "sections": sections,
        }

    def normalize_section(self, section, section_index):
        required = ("name", "type", "flags", "alignment", "size")
        missing = [name for name in required if name not in section]
        if missing:
            raise ValueError(f"section alanları eksik: {', '.join(missing)}")
        section_type = section["type"]
        if section_type not in ("PROGBITS", "NOBITS"):
            raise ValueError(f"geçersiz section tipi: {section_type}")
        alignment = int(section["alignment"])
        size = int(section["size"])
        if alignment <= 0 or alignment & (alignment - 1):
            raise ValueError(f"section '{section['name']}' hizalaması power-of-two olmalı")
        data = bytearray()
        for value in section.get("data", []):
            byte = int(str(value), 16)
            if byte < 0 or byte > 0xFF:
                raise ValueError(f"section '{section['name']}' geçersiz byte içeriyor: {value}")
            data.append(byte)
        if section_type == "PROGBITS" and len(data) != size:
            raise ValueError(f"section '{section['name']}' size/data uzunluğu eşleşmiyor")
        if section_type == "NOBITS" and data:
            raise ValueError(f"NOBITS section '{section['name']}' veri içeremez")
        return {
            "index": section_index,
            "name": section["name"],
            "type": section_type,
            "flags": section["flags"],
            "alignment": alignment,
            "size": size,
            "data": data,
            "layout": {},
            "placed": False,
        }

    def convert_v1_sections(self, raw, path):
        text = bytearray()
        for entry in raw.get("text", []):
            word = int(str(entry), 16)
            text.extend((word >> shift) & 0xFF for shift in (0, 8, 16, 24))
        data = bytearray(self.data_entries_to_bytes(raw.get("data", []), path))
        return [
            {
                "index": 0,
                "name": ".text",
                "type": "PROGBITS",
                "flags": "ax",
                "alignment": 4,
                "size": len(text),
                "data": text,
                "layout": {},
                "placed": False,
            },
            {
                "index": 1,
                "name": ".data",
                "type": "PROGBITS",
                "flags": "aw",
                "alignment": 4,
                "size": len(data),
                "data": data,
                "layout": {},
                "placed": False,
            },
        ]

    def place_sections(self, objects, script):
        outputs = []
        for definition in script.sections:
            region = self.regions.get(definition.region)
            if not region:
                self.errors.append(
                    f"Output section '{definition.name}' bilinmeyen region kullanıyor: '{definition.region}'"
                )
                continue
            try:
                cursor = (
                    evaluate_expression(definition.start_expr, region["cursor"], self.regions)
                    if definition.start_expr
                    else region["cursor"]
                )
            except LinkerScriptError as exc:
                self.errors.append(f"Output section '{definition.name}': {exc}")
                continue
            start = cursor
            if cursor < region["cursor"]:
                self.errors.append(f"Output section '{definition.name}' önceki section ile çakışıyor.")
                continue
            placed = []
            for command in definition.commands:
                if isinstance(command, LocationAssignment):
                    try:
                        next_cursor = evaluate_expression(command.expression, cursor, self.regions)
                    except LinkerScriptError as exc:
                        self.errors.append(f"Output section '{definition.name}': {exc}")
                        continue
                    if next_cursor < cursor:
                        self.errors.append(f"Output section '{definition.name}' location counter geriye taşınamaz.")
                    else:
                        cursor = next_cursor
                    continue
                for obj, section in self.match_sections(objects, command):
                    if section["placed"]:
                        continue
                    cursor = align_up(cursor, section["alignment"])
                    self.validate_region_flags(region, section, obj)
                    section["layout"] = {
                        "address": cursor,
                        "output_section": definition.name,
                        "region": region["name"],
                        "noload": definition.noload or section["type"] == "NOBITS",
                    }
                    section["placed"] = True
                    placed.append({"object": obj["name"], "section": section["name"], "address": cursor, "size": section["size"]})
                    cursor += section["size"]
            self.check_region_bounds(region, cursor, definition.name)
            region["cursor"] = max(region["cursor"], cursor)
            outputs.append(
                {
                    "name": definition.name,
                    "region": region["name"],
                    "address": start,
                    "size": cursor - start,
                    "noload": definition.noload,
                    "inputs": placed,
                }
            )

        for obj in objects:
            for section in obj["sections"]:
                referenced = any(
                    info.get("section") == section["name"] for info in obj["symbols"].values()
                ) or any(
                    relocation.get("section") == section["name"] for relocation in obj["relocations"]
                )
                if not section["placed"] and (section["size"] or referenced):
                    self.errors.append(f"Orphan input section: {obj['name']}({section['name']})")
                elif not section["placed"]:
                    section["layout"] = {
                        "address": 0,
                        "output_section": None,
                        "region": None,
                        "noload": section["type"] == "NOBITS",
                    }
        return outputs

    def match_sections(self, objects, selector):
        for obj in objects:
            if not (
                selector.object_pattern == "*"
                or fnmatch.fnmatchcase(obj["name"], selector.object_pattern)
                or fnmatch.fnmatchcase(obj["path"], selector.object_pattern)
            ):
                continue
            for section in obj["sections"]:
                if fnmatch.fnmatchcase(section["name"], selector.section_pattern):
                    yield obj, section

    def validate_region_flags(self, region, section, obj):
        required = ""
        if "x" in section["flags"]:
            required += "x"
        if "w" in section["flags"]:
            required += "w"
        if "a" in section["flags"] and "w" not in section["flags"] and "x" not in section["flags"]:
            required += "r"
        missing = [flag for flag in required if flag not in region["flags"]]
        if missing:
            self.errors.append(
                f"{obj['name']}({section['name']}) region '{region['name']}' ile uyumsuz; eksik flag: {''.join(missing)}"
            )

    def check_region_bounds(self, region, cursor, context):
        if cursor > region["origin"] + region["length"]:
            self.errors.append(
                f"{context}, memory region '{region['name']}' kapasitesini aşıyor "
                f"(son=0x{cursor:X}, limit=0x{region['origin'] + region['length']:X})."
            )

    def build_global_symbols(self, objects):
        symbols = {}
        for obj in objects:
            for name, info in obj["symbols"].items():
                if info.get("visibility") != "global" or info.get("section") == "UNDEF":
                    continue
                if name in symbols:
                    self.errors.append(f"Duplicate global symbol '{name}': {symbols[name]['object']} ve {obj['name']}")
                    continue
                symbols[name] = self.symbol_record(obj, name, info)
        return symbols

    def validate_extern_symbols(self, objects, global_symbols):
        for obj in objects:
            for name, info in obj["symbols"].items():
                if info.get("visibility") == "extern" and name not in global_symbols:
                    self.errors.append(f"Unresolved extern symbol '{name}' in {obj['name']}")

    def symbol_record(self, obj, name, info):
        section_name = info.get("section")
        if section_name == "UNDEF":
            address = int(info.get("offset", 0))
        else:
            section = self.find_section(obj, section_name)
            address = section["layout"]["address"] + int(info.get("offset", 0))
        return {
            "address": address,
            "section": section_name,
            "offset": int(info.get("offset", 0)),
            "visibility": info.get("visibility", "local"),
            "object": obj["name"],
        }

    def find_section(self, obj, name):
        for section in obj["sections"]:
            if section["name"] == name:
                return section
        raise ValueError(f"{obj['name']}: bilinmeyen section '{name}'")

    def resolve_symbol(self, obj, name, globals_):
        local = obj["symbols"].get(name)
        if local and local.get("section") != "UNDEF":
            return self.symbol_record(obj, name, local)
        return globals_.get(name)

    def apply_relocations(self, objects, global_symbols):
        applied = []
        for obj in objects:
            for relocation in obj["relocations"]:
                section_name = relocation.get("section")
                try:
                    section = self.find_section(obj, section_name)
                    offset = int(relocation["offset"])
                except (ValueError, KeyError) as exc:
                    self.errors.append(f"{obj['name']}: geçersiz relocation: {exc}")
                    continue
                if section["type"] != "PROGBITS" or offset < 0 or offset + 4 > section["size"] or offset % 4:
                    self.errors.append(f"{obj['name']}({section_name}): relocation offset aralık dışında: {offset}")
                    continue
                symbol_name = relocation.get("symbol")
                symbol = self.resolve_symbol(obj, symbol_name, global_symbols)
                if not symbol:
                    self.errors.append(f"Unresolved symbol '{symbol_name}' referenced by {obj['name']}")
                    continue
                original = int.from_bytes(section["data"][offset:offset + 4], "little")
                patch_address = section["layout"]["address"] + offset
                try:
                    patched = self.patch_word(original, relocation.get("type"), symbol["address"], patch_address)
                except ValueError as exc:
                    self.errors.append(f"{obj['name']}({section_name})+0x{offset:X}: {exc}")
                    continue
                section["data"][offset:offset + 4] = patched.to_bytes(4, "little")
                applied.append(
                    {
                        "object": obj["name"],
                        "section": section_name,
                        "offset": offset,
                        "patch_address": patch_address,
                        "type": relocation.get("type"),
                        "symbol": symbol_name,
                        "target_address": symbol["address"],
                        "original": to_hex_word(original),
                        "patched": to_hex_word(patched),
                    }
                )
        return applied

    def build_region_images(self, objects):
        images = {name: {} for name in self.regions}
        for obj in objects:
            for section in obj["sections"]:
                if not section["placed"] or section["layout"]["noload"] or section["type"] == "NOBITS":
                    continue
                image = images[section["layout"]["region"]]
                base = section["layout"]["address"]
                for offset, byte in enumerate(section["data"]):
                    address = base + offset
                    if address in image:
                        self.errors.append(f"Yüklenebilir veri çakışması: 0x{address:X}")
                    image[address] = byte

        result = {}
        for name, region in self.regions.items():
            image = images[name]
            words = []
            if image:
                last = align_up(max(image) + 1, 4)
                for address in range(region["origin"], last, 4):
                    value = sum(image.get(address + index, 0) << (8 * index) for index in range(4))
                    words.append(to_hex_word(value))
            result[name] = {"memory_words": words}
        return result

    def write_outputs(self, linked_object, output_prefix, loader_dir=None):
        output_dir = os.path.dirname(os.path.abspath(output_prefix))
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        json_path = f"{output_prefix}.linked.json"
        with open(json_path, "w", encoding="utf-8") as json_file:
            json.dump(linked_object, json_file, indent=4)
        loader_path = f"{output_prefix}.picoimg"
        if loader_dir:
            loader_path = os.path.join(loader_dir, f"{os.path.basename(output_prefix)}.picoimg")
        loader_image_path = write_loader_image(linked_object, loader_path)
        region_paths = {}
        for region in linked_object["memory_regions"]:
            if not region["memory_words"]:
                continue
            path = f"{output_prefix}.{region['name']}.hex"
            with open(path, "w", encoding="utf-8") as hex_file:
                for word in region["memory_words"]:
                    hex_file.write(f"{word[2:]}\n")
            region_paths[region["name"]] = os.path.abspath(path)
        return {
            "loader_image": loader_image_path,
            "json": os.path.abspath(json_path),
            "regions": region_paths,
        }

    def data_entries_to_bytes(self, data_entries, path):
        data_bytes = []
        for index, entry in enumerate(data_entries):
            try:
                text = str(entry).strip()
                if not text.lower().startswith("0x"):
                    raise ValueError("0x ile başlamalı")
                digits = text[2:]
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

    def patch_word(self, word, relocation_type, target_address, patch_address):
        if relocation_type == "R_RISCV_HI20":
            opcode = word & 0x7F
            if opcode == 0x17:
                value = target_address - patch_address
            elif opcode == 0x37:
                value = target_address
            else:
                raise ValueError("R_RISCV_HI20 sadece auipc veya lui üzerinde uygulanabilir")
            return (word & 0x00000FFF) | ((((value + 0x800) >> 12) & 0xFFFFF) << 12)
        if relocation_type == "R_RISCV_LO12_I":
            return (word & 0x000FFFFF) | ((target_address & 0xFFF) << 20)
        if relocation_type == "R_RISCV_LO12_S":
            imm = target_address & 0xFFF
            word &= ~((0x7F << 25) | (0x1F << 7)) & 0xFFFFFFFF
            return word | (((imm >> 5) & 0x7F) << 25) | ((imm & 0x1F) << 7)
        if relocation_type == "R_RISCV_BRANCH":
            return self.patch_branch(word, target_address - patch_address)
        if relocation_type == "R_RISCV_JAL":
            return self.patch_jal(word, target_address - patch_address)
        raise ValueError(f"desteklenmeyen relocation tipi: {relocation_type}")

    def patch_branch(self, word, offset):
        if offset % 2 or offset < -4096 or offset > 4094:
            raise ValueError(f"branch hedef offset'i 13-bit hizalı aralık dışında: {offset}")
        imm = offset & 0x1FFF
        word &= ~((1 << 31) | (0x3F << 25) | (0xF << 8) | (1 << 7)) & 0xFFFFFFFF
        return word | (((imm >> 12) & 1) << 31) | (((imm >> 5) & 0x3F) << 25) | (((imm >> 1) & 0xF) << 8) | (((imm >> 11) & 1) << 7)

    def patch_jal(self, word, offset):
        if offset % 2 or offset < -1048576 or offset > 1048574:
            raise ValueError(f"jal hedef offset'i 21-bit hizalı aralık dışında: {offset}")
        imm = offset & 0x1FFFFF
        word &= 0x00000FFF
        return word | (((imm >> 20) & 1) << 31) | (((imm >> 1) & 0x3FF) << 21) | (((imm >> 11) & 1) << 20) | (((imm >> 12) & 0xFF) << 12)


def build_arg_parser():
    parser = argparse.ArgumentParser(description="PicoRV linker script tabanlı JSON object linker")
    parser.add_argument("objects", nargs="+", help="Linklenecek .o JSON object dosyaları")
    parser.add_argument("-T", "--script", required=True, help="GNU-benzeri linker script (.ld)")
    parser.add_argument("-o", "--output", default=os.path.join(LINKER_OUTPUT_DIR, "program"), help="Çıktı prefix'i")
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    ensure_output_dirs()
    linker = PicoRVLinker(args.script)
    linked_object, errors = linker.link(args.objects)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    paths = linker.write_outputs(linked_object, args.output, loader_dir=LOADER_OUTPUT_DIR)
    print(f"Loader image: {paths['loader_image']}")
    print(f"Linked JSON: {paths['json']}")
    for region, path in paths["regions"].items():
        print(f"{region} HEX: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
