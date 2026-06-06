import re

opcode_table = {
    "add": {"format": "R", "opcode": "0110011", "funct3": "000", "funct7": "0000000"},
    "sub": {"format": "R", "opcode": "0110011", "funct3": "000", "funct7": "0100000"},
    "and": {"format": "R", "opcode": "0110011", "funct3": "111", "funct7": "0000000"},
    "or":  {"format": "R", "opcode": "0110011", "funct3": "110", "funct7": "0000000"},
    "xor": {"format": "R", "opcode": "0110011", "funct3": "100", "funct7": "0000000"},
    "sll": {"format": "R", "opcode": "0110011", "funct3": "001", "funct7": "0000000"},
    "srl": {"format": "R", "opcode": "0110011", "funct3": "101", "funct7": "0000000"},
    "sra": {"format": "R", "opcode": "0110011", "funct3": "101", "funct7": "0100000"},
    "addi":{"format": "I", "opcode": "0010011", "funct3": "000"},
    "slli":{"format": "I_SHIFT", "opcode": "0010011", "funct3": "001", "funct7": "0000000"},
    "lw":  {"format": "I", "opcode": "0000011", "funct3": "010"},
    "lh":  {"format": "I", "opcode": "0000011", "funct3": "001"},
    "lbu": {"format": "I", "opcode": "0000011", "funct3": "100"},
    "jalr":{"format": "I", "opcode": "1100111", "funct3": "000"},
    "sw":  {"format": "S", "opcode": "0100011", "funct3": "010"},
    "sh":  {"format": "S", "opcode": "0100011", "funct3": "001"},
    "sb":  {"format": "S", "opcode": "0100011", "funct3": "000"},
    "beq": {"format": "B", "opcode": "1100011", "funct3": "000"},
    "bne": {"format": "B", "opcode": "1100011", "funct3": "001"},
    "blt": {"format": "B", "opcode": "1100011", "funct3": "100"},
    "bge": {"format": "B", "opcode": "1100011", "funct3": "101"},
    "jal": {"format": "J", "opcode": "1101111"},
    "lui": {"format": "U", "opcode": "0110111"},
    "auipc":{"format": "U", "opcode": "0010111"},
    "ecall": {"format": "ENV", "word": "00000000000000000000000001110011"},
    "ebreak": {"format": "ENV", "word": "00000000000100000000000001110011"}
}

directives = {
    ".text", ".data", ".rodata", ".bss", ".init", ".section",
    ".word", ".byte", ".zero", ".space", ".align",
    ".end", ".global", ".extern"
}

operand_counts = {
    "add": 3, "sub": 3, "addi": 3, "slli": 3, "and": 3, "or": 3, "xor": 3, "sll": 3, "srl": 3, "sra": 3,
    "lw": 2, "lh": 2, "lbu": 2, "sw": 2, "sh": 2, "sb": 2, 
    "beq": 3, "bne": 3, "blt": 3, "bge": 3, "jal": 2, "jalr": 3,
    "lui": 2, "auipc": 2,
    "ecall": 0, "ebreak": 0,
    ".text": 0, ".data": 0, ".rodata": 0, ".bss": 0, ".init": 0,
    ".section": -1, ".end": 0, ".word": -1, ".byte": -1,
    ".zero": 1, ".space": 1, ".align": 1,
    ".global": 1, ".extern": 1
}

def validate_and_get_reg(reg_str):
    if not reg_str.startswith('x'):
        raise ValueError(f"Register '{reg_str}' hatalı. 'x' ile başlamalı (ör: x1).")
    try:
        num = int(reg_str[1:])
        if num < 0 or num > 31:
            raise ValueError(f"Register '{reg_str}' sınırların dışında. (0-31 aralığında olmalı)")
        return format(num, '05b')
    except ValueError as e:
        if "invalid literal" in str(e):
            raise ValueError(f"'{reg_str}' geçerli bir register formatı değil.")
        raise e

def validate_and_get_imm(imm_str, bits):
    try:
        imm_int = int(imm_str, 0)
        min_val = -(1 << (bits - 1))
        max_val = (1 << (bits - 1)) - 1
        if imm_int < min_val or imm_int > max_val:
            raise ValueError(f"Değer '{imm_str}' {bits}-bit sınırlarına sığmıyor ({min_val} ile {max_val} arası).")
        if imm_int < 0:
            imm_int = (1 << bits) + imm_int
        return format(imm_int, f'0{bits}b')
    except ValueError as e:
        if "invalid literal" in str(e):
            raise ValueError(f"'{imm_str}' geçerli bir sayı değil.")
        raise e

def validate_and_get_byte(byte_str):
    try:
        byte_int = int(byte_str, 0)
        if byte_int < -128 or byte_int > 255:
            raise ValueError(f"Değer '{byte_str}' 8-bit sınırlarına sığmıyor (-128 ile 255 arası).")
        if byte_int < 0:
            byte_int = (1 << 8) + byte_int
        return format(byte_int, '08b')
    except ValueError as e:
        if "invalid literal" in str(e):
            raise ValueError(f"'{byte_str}' geçerli bir sayı değil.")
        raise e

class PicoRVAssembler:
    def __init__(self):
        self.symbol_table = {}   
        self.machine_code = []   
        self.data_code = []      
        self.relocations = []    
        self.errors = []
        
        self.TEXT_BASE = 0x00000000 
        self.DATA_BASE = 0x00000000 
        self.text_pc = self.TEXT_BASE
        self.data_pc = self.DATA_BASE
        self.current_section = ".text"

    def parse_line(self, line):
        line = line.split('#')[0].strip()
        if not line:
            return None, []
        label = None
        if ':' in line:
            parts = line.split(':', 1)
            label = parts[0].strip()
            line = parts[1].strip()
        tokens = [t.strip() for t in re.split(r'[,\s]+', line) if t.strip()]
        return label, tokens

    def process_pass_one_tokens(self, tokens, line_num):
        if not tokens:
            return
        instruction = tokens[0]
        if instruction in [".text", ".data"]:
            self.current_section = instruction
        elif instruction == ".global":
            lbl = tokens[1]
            if lbl not in self.symbol_table:
                self.symbol_table[lbl] = {"section": "UNDEF", "offset": 0, "visibility": "global"}
            else:
                self.symbol_table[lbl]["visibility"] = "global"
        elif instruction == ".extern":
            lbl = tokens[1]
            if lbl not in self.symbol_table:
                self.symbol_table[lbl] = {"section": "UNDEF", "offset": 0, "visibility": "extern"}
        elif instruction in opcode_table:
            if self.current_section != ".text":
                self.errors.append(f"Satır {line_num}: Kodlar sadece .text kısmında olmalıdır.")
            self.text_pc += 4
        elif instruction == ".word":
            self.data_pc += 4 * (len(tokens) - 1)
        elif instruction == ".byte":
            self.data_pc += 1 * (len(tokens) - 1)
        elif instruction not in directives:
            self.errors.append(f"Satır {line_num}: Bilinmeyen komut/direktif '{instruction}'")

    def pass_one(self, source_code):
        self.text_pc = self.TEXT_BASE
        self.data_pc = self.DATA_BASE
        self.current_section = ".text"
        self.symbol_table.clear()
        
        for i, line in enumerate(source_code):
            line_num = i + 1
            try:
                label, tokens = self.parse_line(line)
                if label:
                    if label in self.symbol_table and self.symbol_table[label]["section"] != "UNDEF":
                        self.errors.append(f"Satır {line_num}: '{label}' etiketi zaten tanımlanmış.")
                    else:
                        is_global = False
                        if label in self.symbol_table and self.symbol_table[label]["visibility"] == "global":
                            is_global = True
                        self.symbol_table[label] = {
                            "section": self.current_section,
                            "offset": self.text_pc if self.current_section == ".text" else self.data_pc,
                            "visibility": "global" if is_global else "local"
                        }
                self.process_pass_one_tokens(tokens, line_num)
            except Exception as e:
                self.errors.append(f"Satır {line_num}: Beklenmeyen hata - {str(e)}")

    def pass_two(self, source_code):
        self.text_pc = self.TEXT_BASE
        self.data_pc = self.DATA_BASE
        self.current_section = ".text"
        self.machine_code.clear()
        self.data_code.clear()
        self.relocations.clear()
        
        for i, line in enumerate(source_code):
            line_num = i + 1
            label, tokens = self.parse_line(line)
            
            if not tokens:
                continue
                
            instruction = tokens[0]
            if instruction in [".text", ".data"]:
                self.current_section = instruction
                continue
            if instruction in [".global", ".extern", ".end"]:
                continue
                
            if instruction == ".word":
                for val in tokens[1:]:
                    try:
                        bin_val = validate_and_get_imm(val, 32)
                        hex_val = hex(int(bin_val, 2))[2:].zfill(8).upper()
                        self.data_code.append(f"0x{hex_val}")
                        self.data_pc += 4
                    except Exception as e:
                        self.errors.append(f"Satır {line_num}: .word hatası - {str(e)}")
                continue

            if instruction == ".byte":
                for val in tokens[1:]:
                    try:
                        bin_val = validate_and_get_byte(val)
                        hex_val = hex(int(bin_val, 2))[2:].zfill(2).upper()
                        self.data_code.append(f"0x{hex_val}")
                        self.data_pc += 1
                    except Exception as e:
                        self.errors.append(f"Satır {line_num}: .byte hatası - {str(e)}")
                continue
                
            if instruction in opcode_table:
                expected_args = operand_counts.get(instruction, -1)
                actual_args = len(tokens) - 1
                if expected_args != -1 and actual_args != expected_args:
                    self.errors.append(f"Satır {line_num}: '{instruction}' komutu {expected_args} argüman bekler, {actual_args} verildi.")
                    continue

                fmt = opcode_table[instruction]["format"]
                args = tokens[1:]
                
                try:
                    m_code = self.generate_machine_code(instruction, fmt, args, self.text_pc)
                    hex_code = hex(int(m_code, 2))[2:].zfill(8).upper()
                    self.machine_code.append(f"0x{hex_code}")
                except Exception as e:
                    self.errors.append(f"Satır {line_num}: {str(e)}")
                    
                self.text_pc += 4

    def generate_machine_code(self, inst, fmt, args, current_pc):
        op = opcode_table[inst]
        if fmt == "R":
            rd, rs1, rs2 = validate_and_get_reg(args[0]), validate_and_get_reg(args[1]), validate_and_get_reg(args[2])
            return f"{op['funct7']}{rs2}{rs1}{op['funct3']}{rd}{op['opcode']}"
            
        elif fmt == "I":
            if inst in ["lw", "lh", "lbu"]:
                rd = validate_and_get_reg(args[0])
                match = re.match(r'^(-?(?:0x[0-9a-fA-F]+|\d+)|[a-zA-Z_]\w*)\((x\d+)\)$', args[1])
                if not match:
                    raise ValueError(f"Bellek adresi formatı hatalı: '{args[1]}'. Doğru format: imm(reg) veya label(reg)")
                imm_part = match.group(1)
                rs1 = validate_and_get_reg(match.group(2))
                
                if imm_part.lstrip('-').replace('0x','',1).isdigit():
                    imm = validate_and_get_imm(imm_part, 12)
                else:
                    self.relocations.append({"section": self.current_section, "offset": current_pc, "type": "R_RISCV_LO12_I", "symbol": imm_part})
                    imm = "000000000000"
            else:
                rd, rs1 = validate_and_get_reg(args[0]), validate_and_get_reg(args[1])
                imm_part = args[2]
                if imm_part.lstrip('-').replace('0x','',1).isdigit():
                    imm = validate_and_get_imm(imm_part, 12)
                else:
                    self.relocations.append({"section": self.current_section, "offset": current_pc, "type": "R_RISCV_LO12_I", "symbol": imm_part})
                    imm = "000000000000"
            return f"{imm}{rs1}{op['funct3']}{rd}{op['opcode']}"

        elif fmt == "I_SHIFT":
            rd, rs1 = validate_and_get_reg(args[0]), validate_and_get_reg(args[1])
            try:
                shamt = int(args[2], 0)
            except ValueError:
                raise ValueError(f"'{args[2]}' geçerli bir shift miktarı değil.")
            if shamt < 0 or shamt > 31:
                raise ValueError(f"Shift miktarı '{args[2]}' 5-bit sınırlarına sığmıyor (0 ile 31 arası).")
            shamt_bin = format(shamt, '05b')
            return f"{op['funct7']}{shamt_bin}{rs1}{op['funct3']}{rd}{op['opcode']}"
            
        elif fmt == "S":
            rs2 = validate_and_get_reg(args[0])
            match = re.match(r'^(-?(?:0x[0-9a-fA-F]+|\d+)|[a-zA-Z_]\w*)\((x\d+)\)$', args[1])
            if not match:
                raise ValueError(f"Bellek adresi formatı hatalı: '{args[1]}'. Doğru format: imm(reg) veya label(reg)")
            imm_part = match.group(1)
            rs1 = validate_and_get_reg(match.group(2))
            
            if imm_part.lstrip('-').replace('0x','',1).isdigit():
                imm_val = validate_and_get_imm(imm_part, 12)
            else:
                self.relocations.append({"section": self.current_section, "offset": current_pc, "type": "R_RISCV_LO12_S", "symbol": imm_part})
                imm_val = "000000000000"
            return f"{imm_val[0:7]}{rs2}{rs1}{op['funct3']}{imm_val[7:12]}{op['opcode']}"
            
        elif fmt == "B":
            rs1, rs2 = validate_and_get_reg(args[0]), validate_and_get_reg(args[1])
            target_label = args[2]
            offset = 0
            if target_label in self.symbol_table and self.symbol_table[target_label]["section"] == self.current_section:
                offset = self.symbol_table[target_label]["offset"] - current_pc
                imm_bin = validate_and_get_imm(str(offset), 13)
            else:
                self.relocations.append({"section": self.current_section, "offset": current_pc, "type": "R_RISCV_BRANCH", "symbol": target_label})
                imm_bin = "0000000000000"
                
            return f"{imm_bin[0]}{imm_bin[2:8]}{rs2}{rs1}{op['funct3']}{imm_bin[8:12]}{imm_bin[1]}{op['opcode']}"
            
        elif fmt == "J":
            rd = validate_and_get_reg(args[0])
            target_label = args[1]
            offset = 0
            if target_label in self.symbol_table and self.symbol_table[target_label]["section"] == self.current_section and self.symbol_table[target_label]["visibility"] == "local":
                 offset = self.symbol_table[target_label]["offset"] - current_pc
                 imm_bin = validate_and_get_imm(str(offset), 21)
            else:
                 self.relocations.append({"section": self.current_section, "offset": current_pc, "type": "R_RISCV_JAL", "symbol": target_label})
                 imm_bin = "000000000000000000000"
            return f"{imm_bin[0]}{imm_bin[10:20]}{imm_bin[9]}{imm_bin[1:9]}{rd}{op['opcode']}"

        elif fmt == "U":
            rd = validate_and_get_reg(args[0])
            imm_part = args[1]
            if imm_part.lstrip('-').replace('0x','',1).isdigit():
                 imm_bin = validate_and_get_imm(imm_part, 20)
            else:
                 self.relocations.append({"section": self.current_section, "offset": current_pc, "type": "R_RISCV_HI20", "symbol": imm_part})
                 imm_bin = "00000000000000000000"
            return f"{imm_bin}{rd}{op['opcode']}"

        elif fmt == "ENV":
            return op["word"]

    def assemble(self, source_code):
        self.errors = []
        self.pass_one(source_code)
        if not self.errors:
            self.pass_two(source_code)
            
        obj_file = {
            "text": self.machine_code,
            "data": self.data_code,
            "symbols": self.symbol_table,
            "relocations": self.relocations
        }
        return obj_file, self.errors


class PicoRVAssemblerV2(PicoRVAssembler):
    SECTION_DEFAULTS = {
        ".text": ("PROGBITS", "ax", 4),
        ".init": ("PROGBITS", "ax", 4),
        ".rodata": ("PROGBITS", "a", 4),
        ".data": ("PROGBITS", "aw", 4),
        ".bss": ("NOBITS", "aw", 4),
    }

    def __init__(self):
        super().__init__()
        self.sections = {}
        self.section_offsets = {}
        self.current_section = ".text"

    def ensure_section(self, name, section_type=None, flags=None, alignment=None, explicit=False):
        defaults = self.SECTION_DEFAULTS.get(name)
        if defaults:
            default_type, default_flags, default_alignment = defaults
            section_type = section_type or default_type
            flags = flags if flags is not None else default_flags
            alignment = alignment or default_alignment
        elif not explicit:
            raise ValueError(
                f"Özel section '{name}' için .section adı, \"flags\", @progbits|@nobits kullanılmalı."
            )
        else:
            section_type = section_type or "PROGBITS"
            flags = flags if flags is not None else ""
            alignment = alignment or 1

        if section_type not in ("PROGBITS", "NOBITS"):
            raise ValueError(f"Geçersiz section tipi: {section_type}")

        existing = self.sections.get(name)
        if existing:
            if existing["type"] != section_type or existing["flags"] != flags:
                raise ValueError(f"Section '{name}' çelişkili özelliklerle yeniden tanımlandı.")
            return existing

        section = {
            "name": name,
            "type": section_type,
            "flags": flags,
            "alignment": alignment,
            "size": 0,
            "data": [],
        }
        self.sections[name] = section
        self.section_offsets[name] = 0
        return section

    def switch_section(self, tokens):
        directive = tokens[0]
        if directive != ".section":
            self.ensure_section(directive)
            self.current_section = directive
            return

        if len(tokens) < 2:
            raise ValueError(".section bir section adı bekler.")
        name = tokens[1]
        defaults = self.SECTION_DEFAULTS.get(name)
        flags = tokens[2].strip('"') if len(tokens) >= 3 else (defaults[1] if defaults else None)
        type_token = tokens[3].lower() if len(tokens) >= 4 else None
        section_type = None
        if type_token:
            if type_token == "@progbits":
                section_type = "PROGBITS"
            elif type_token == "@nobits":
                section_type = "NOBITS"
            else:
                raise ValueError(f"Geçersiz .section tipi: {tokens[3]}")
        if not defaults and (flags is None or section_type is None):
            raise ValueError(
                f"Özel section '{name}' için flags ve @progbits|@nobits zorunludur."
            )
        self.ensure_section(name, section_type, flags, explicit=True)
        self.current_section = name

    @staticmethod
    def parse_count(token, directive):
        try:
            value = int(token, 0)
        except ValueError:
            raise ValueError(f"{directive} için geçersiz sayı: '{token}'")
        if value < 0:
            raise ValueError(f"{directive} negatif değer kabul etmez.")
        return value

    @staticmethod
    def validate_alignment(token):
        alignment = PicoRVAssemblerV2.parse_count(token, ".align")
        if alignment == 0 or alignment & (alignment - 1):
            raise ValueError(".align pozitif bir power-of-two byte değeri olmalı.")
        return alignment

    def current_offset(self):
        return self.section_offsets[self.current_section]

    def advance(self, count):
        self.section_offsets[self.current_section] += count
        self.sections[self.current_section]["size"] = self.section_offsets[self.current_section]

    def process_v2_tokens(self, tokens, line_num):
        if not tokens:
            return
        instruction = tokens[0]
        if instruction in (".text", ".data", ".rodata", ".bss", ".init", ".section"):
            self.switch_section(tokens)
        elif instruction == ".global":
            if len(tokens) != 2:
                raise ValueError(".global bir sembol bekler.")
            name = tokens[1]
            if name not in self.symbol_table:
                self.symbol_table[name] = {"section": "UNDEF", "offset": 0, "visibility": "global"}
            else:
                self.symbol_table[name]["visibility"] = "global"
        elif instruction == ".extern":
            if len(tokens) != 2:
                raise ValueError(".extern bir sembol bekler.")
            name = tokens[1]
            if name not in self.symbol_table:
                self.symbol_table[name] = {"section": "UNDEF", "offset": 0, "visibility": "extern"}
        elif instruction in opcode_table:
            section = self.sections[self.current_section]
            if "x" not in section["flags"] or section["type"] != "PROGBITS":
                raise ValueError("Komutlar yalnız executable PROGBITS section içinde olabilir.")
            self.advance(4)
        elif instruction == ".word":
            self.require_progbits(instruction)
            self.advance(4 * (len(tokens) - 1))
        elif instruction == ".byte":
            self.require_progbits(instruction)
            self.advance(len(tokens) - 1)
        elif instruction in (".zero", ".space"):
            if len(tokens) != 2:
                raise ValueError(f"{instruction} bir boyut bekler.")
            self.advance(self.parse_count(tokens[1], instruction))
        elif instruction == ".align":
            if len(tokens) != 2:
                raise ValueError(".align bir hizalama değeri bekler.")
            alignment = self.validate_alignment(tokens[1])
            section = self.sections[self.current_section]
            section["alignment"] = max(section["alignment"], alignment)
            self.advance((-self.current_offset()) % alignment)
        elif instruction == ".end":
            return
        elif instruction not in directives:
            raise ValueError(f"Bilinmeyen komut/direktif '{instruction}'")

    def require_progbits(self, directive):
        if self.sections[self.current_section]["type"] != "PROGBITS":
            raise ValueError(f"{directive}, NOBITS section içinde kullanılamaz.")

    def pass_one(self, source_code):
        self.sections = {}
        self.section_offsets = {}
        self.symbol_table.clear()
        self.current_section = ".text"
        self.ensure_section(".text")

        for index, line in enumerate(source_code):
            line_num = index + 1
            try:
                label, tokens = self.parse_line(line)
                if label:
                    if label in self.symbol_table and self.symbol_table[label]["section"] != "UNDEF":
                        raise ValueError(f"'{label}' etiketi zaten tanımlanmış.")
                    visibility = "global" if (
                        label in self.symbol_table
                        and self.symbol_table[label]["visibility"] == "global"
                    ) else "local"
                    self.symbol_table[label] = {
                        "section": self.current_section,
                        "offset": self.current_offset(),
                        "visibility": visibility,
                    }
                self.process_v2_tokens(tokens, line_num)
            except Exception as exc:
                self.errors.append(f"Satır {line_num}: {exc}")

    def append_bytes(self, values):
        values = list(values)
        section = self.sections[self.current_section]
        section["data"].extend(f"0x{value & 0xFF:02X}" for value in values)
        self.advance(len(values))

    def append_zeros(self, count):
        section = self.sections[self.current_section]
        if section["type"] == "PROGBITS":
            section["data"].extend(["0x00"] * count)
        self.advance(count)

    def pass_two(self, source_code):
        for section in self.sections.values():
            section["data"] = []
            section["size"] = 0
        self.section_offsets = {name: 0 for name in self.sections}
        self.current_section = ".text"
        self.relocations.clear()

        for index, line in enumerate(source_code):
            line_num = index + 1
            try:
                _, tokens = self.parse_line(line)
                if not tokens:
                    continue
                instruction = tokens[0]
                if instruction in (".text", ".data", ".rodata", ".bss", ".init", ".section"):
                    self.switch_section(tokens)
                    continue
                if instruction in (".global", ".extern", ".end"):
                    continue
                if instruction == ".align":
                    alignment = self.validate_alignment(tokens[1])
                    self.append_zeros((-self.current_offset()) % alignment)
                    continue
                if instruction in (".zero", ".space"):
                    self.append_zeros(self.parse_count(tokens[1], instruction))
                    continue
                if instruction == ".word":
                    for value in tokens[1:]:
                        bits = validate_and_get_imm(value, 32)
                        integer = int(bits, 2)
                        self.append_bytes((integer >> shift) & 0xFF for shift in (0, 8, 16, 24))
                    continue
                if instruction == ".byte":
                    for value in tokens[1:]:
                        self.append_bytes([int(validate_and_get_byte(value), 2)])
                    continue
                if instruction in opcode_table:
                    expected = operand_counts.get(instruction, -1)
                    actual = len(tokens) - 1
                    if expected != -1 and actual != expected:
                        raise ValueError(f"'{instruction}' komutu {expected} argüman bekler, {actual} verildi.")
                    offset = self.current_offset()
                    code = self.generate_machine_code(instruction, opcode_table[instruction]["format"], tokens[1:], offset)
                    word = int(code, 2)
                    self.append_bytes((word >> shift) & 0xFF for shift in (0, 8, 16, 24))
                    continue
            except Exception as exc:
                self.errors.append(f"Satır {line_num}: {exc}")

    def assemble(self, source_code):
        self.errors = []
        self.pass_one(source_code)
        if not self.errors:
            self.pass_two(source_code)
        return {
            "format": "picorv-json-object",
            "version": 2,
            "sections": list(self.sections.values()),
            "symbols": self.symbol_table,
            "relocations": self.relocations,
        }, self.errors


PicoRVAssembler = PicoRVAssemblerV2
