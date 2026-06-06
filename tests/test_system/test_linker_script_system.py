# Assembler ve linker script tabanlı linker'ın section yerleşimi, relocation,
# memory region, hata kontrolü ve bölgesel HEX/.picoimg çıktılarını test eder.

import json
import os
import tempfile
import unittest
from pathlib import Path

from src.assembler import PicoRVAssembler
from src.linker import PicoRVLinker
from src.linker_script import LinkerScriptError, evaluate_expression, parse_linker_script


SPLIT_SCRIPT = """
ENTRY(_start);
MEMORY {
    ROM (rx) : ORIGIN = 0x0, LENGTH = 16K;
    RAM (rw) : ORIGIN = 0x10000, LENGTH = 4K;
}
SECTIONS {
    .text : ALIGN(4) { *(.text*) } > ROM
    .rodata : ALIGN(4) { *(.rodata*) } > ROM
    .data : ALIGN(4) { *(.data*) } > RAM
    .bss (NOLOAD) : ALIGN(4) { *(.bss*) } > RAM
}
"""


class LinkerScriptSystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()

    def path(self, name):
        return os.path.join(self.temp.name, name)

    def write_text(self, name, content):
        path = self.path(name)
        with open(path, "w", encoding="utf-8") as output:
            output.write(content)
        return path

    def assemble(self, name, source):
        obj, errors = PicoRVAssembler().assemble(source.strip().splitlines())
        self.assertEqual([], errors)
        path = self.path(name)
        with open(path, "w", encoding="utf-8") as output:
            json.dump(obj, output)
        return path, obj

    def link(self, objects, script=SPLIT_SCRIPT):
        script_path = self.write_text("layout.ld", script)
        return PicoRVLinker(script_path).link(objects)

    def test_parser_supports_memory_selectors_and_expressions(self):
        script = parse_linker_script(SPLIT_SCRIPT)
        self.assertEqual("_start", script.entry)
        self.assertEqual(["ROM", "RAM"], [region.name for region in script.memory])
        regions = {"ROM": {"origin": 3, "length": 16}}
        expression = parse_linker_script(
            "ENTRY(x); MEMORY { R (rwx): ORIGIN=0, LENGTH=1K; } "
            "SECTIONS { .x : ALIGN(8) { *(.x) } > R }"
        ).sections[0].start_expr
        self.assertEqual(8, evaluate_expression(expression, dot=3, regions=regions))

    def test_parser_rejects_unsupported_top_level_construct(self):
        with self.assertRaises(LinkerScriptError):
            parse_linker_script("OUTPUT(foo)")

    def test_assembler_emits_v2_named_progbits_and_nobits_sections(self):
        _, obj = self.assemble(
            "sections.o",
            """
            .section .custom, "a", @progbits
            .byte 1
            .align 4
            .byte 2
            .bss
            buffer:
            .space 12
            """,
        )
        self.assertEqual(2, obj["version"])
        custom = next(section for section in obj["sections"] if section["name"] == ".custom")
        bss = next(section for section in obj["sections"] if section["name"] == ".bss")
        self.assertEqual(5, custom["size"])
        self.assertEqual(["0x01", "0x00", "0x00", "0x00", "0x02"], custom["data"])
        self.assertEqual("NOBITS", bss["type"])
        self.assertEqual(12, bss["size"])
        self.assertEqual([], bss["data"])

    def test_link_places_sections_in_regions_and_omits_bss_image(self):
        object_path, _ = self.assemble(
            "program.o",
            """
            .text
            .global _start
            _start:
            ebreak
            .data
            value:
            .word 0x1234
            .bss
            buffer:
            .space 16
            """,
        )
        linked, errors = self.link([object_path])
        self.assertEqual([], errors)
        sections = {item["section"]: item for item in linked["object_sections"]}
        self.assertEqual(0, sections[".text"]["address"])
        self.assertEqual(0x10000, sections[".data"]["address"])
        self.assertEqual(0x10004, sections[".bss"]["address"])
        regions = {region["name"]: region for region in linked["memory_regions"]}
        self.assertEqual(["0x00100073"], regions["ROM"]["memory_words"])
        self.assertEqual(["0x00001234"], regions["RAM"]["memory_words"])

    def test_hi20_lo12_relocations_use_script_assigned_data_address(self):
        object_path, _ = self.assemble(
            "reloc.o",
            """
            .text
            .global _start
            _start:
            lui x5, value
            lw x6, value(x5)
            .data
            value:
            .word 7
            """,
        )
        linked, errors = self.link([object_path])
        self.assertEqual([], errors)
        self.assertEqual([0x10000, 0x10000], [item["target_address"] for item in linked["applied_relocations"]])
        rom = next(region for region in linked["memory_regions"] if region["name"] == "ROM")
        self.assertEqual("0x000102B7", rom["memory_words"][0])

    def test_v1_object_is_accepted(self):
        v1 = {
            "text": ["0x00100073"],
            "data": [],
            "symbols": {"_start": {"section": ".text", "offset": 0, "visibility": "global"}},
            "relocations": [],
        }
        object_path = self.path("legacy.o")
        with open(object_path, "w", encoding="utf-8") as output:
            json.dump(v1, output)
        linked, errors = self.link([object_path])
        self.assertEqual([], errors)
        self.assertEqual(0, linked["entry"])

    def test_object_selector_and_location_counter_control_order(self):
        start_path, _ = self.assemble(
            "start.o",
            """
            .text
            .global _start
            _start:
            ebreak
            """,
        )
        library_path, _ = self.assemble(
            "library.o",
            """
            .text
            helper:
            ebreak
            """,
        )
        script = """
        ENTRY(_start);
        MEMORY { ROM (rx): ORIGIN=0, LENGTH=1K; }
        SECTIONS {
            .text : {
                start.o(.text)
                . = ALIGN(16);
                *(.text*)
            } > ROM
        }
        """
        linked, errors = self.link([library_path, start_path], script)
        self.assertEqual([], errors)
        sections = {(item["object"], item["section"]): item for item in linked["object_sections"]}
        self.assertEqual(0, sections[("start.o", ".text")]["address"])
        self.assertEqual(16, sections[("library.o", ".text")]["address"])

    def test_script_is_required(self):
        linked, errors = PicoRVLinker().link([])
        self.assertIsNone(linked)
        self.assertTrue(any("Linker script zorunludur" in error for error in errors))

    def test_orphan_section_is_an_error(self):
        object_path, _ = self.assemble(
            "orphan.o",
            """
            .text
            .global _start
            _start:
            ebreak
            .section .custom, "a", @progbits
            .byte 1
            """,
        )
        _, errors = self.link([object_path])
        self.assertTrue(any("Orphan input section" in error for error in errors))

    def test_region_overflow_is_an_error(self):
        object_path, _ = self.assemble(
            "overflow.o",
            """
            .text
            .global _start
            _start:
            .space 8
            """,
        )
        script = """
        ENTRY(_start);
        MEMORY { ROM (rx): ORIGIN=0, LENGTH=4; }
        SECTIONS { .text : { *(.text*) } > ROM }
        """
        _, errors = self.link([object_path], script)
        self.assertTrue(any("kapasitesini aşıyor" in error for error in errors))

    def test_region_flag_mismatch_is_an_error(self):
        object_path, _ = self.assemble(
            "flags.o",
            """
            .text
            .global _start
            _start:
            ebreak
            """,
        )
        script = """
        ENTRY(_start);
        MEMORY { RAM (rw): ORIGIN=0, LENGTH=1K; }
        SECTIONS { .text : { *(.text*) } > RAM }
        """
        _, errors = self.link([object_path], script)
        self.assertTrue(any("eksik flag: x" in error for error in errors))

    def test_region_hex_output_is_written_per_loadable_region(self):
        object_path, _ = self.assemble(
            "output.o",
            """
            .text
            .global _start
            _start:
            ebreak
            .bss
            .space 4
            """,
        )
        linked, errors = self.link([object_path])
        self.assertEqual([], errors)
        paths = PicoRVLinker().write_outputs(linked, self.path("program"))
        self.assertIn("ROM", paths["regions"])
        self.assertNotIn("RAM", paths["regions"])
        self.assertTrue(os.path.exists(paths["loader_image"]))
        self.assertTrue(os.path.exists(paths["json"]))

    def test_current_asm_scenarios_run_with_project_linker_script(self):
        tests_dir = Path(__file__).parents[1]
        scenarios = [
            "karasimsek",
            "ileri_geri_sayac",
            "secimli_mat",
            "bram_sinir_zorlama",
        ]
        script_path = str(tests_dir / "project.ld")
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                objects = []
                for source_path in sorted((tests_dir / scenario).glob("*.asm")):
                    obj, errors = PicoRVAssembler().assemble(source_path.read_text(encoding="utf-8").splitlines())
                    self.assertEqual([], errors)
                    object_path = self.path(f"{scenario}_{source_path.stem}.o")
                    with open(object_path, "w", encoding="utf-8") as output:
                        json.dump(obj, output)
                    objects.append(object_path)
                _, errors = PicoRVLinker(script_path).link(objects)
                self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
