import re  # Düzenli ifade (regex) işlemleri için kullanılır

# --- Core Assembler Verileri ---
# RISC-V komut setindeki her komutun ikili (binary) kodlama bilgilerini içerir.
# 'format': Komutun türü (R, I, S, B, J)
# 'opcode': 7-bit işlem kodu
# 'funct3': Komutu aynı opcode içinde ayırt eden 3-bit alan
# 'funct7': R-format komutlarını ayrıştıran 7-bit alan
opcode_table = {
    "add": {"format": "R", "opcode": "0110011", "funct3": "000", "funct7": "0000000"},
    "sub": {"format": "R", "opcode": "0110011", "funct3": "000", "funct7": "0100000"},
    "and": {"format": "R", "opcode": "0110011", "funct3": "111", "funct7": "0000000"},
    "or":  {"format": "R", "opcode": "0110011", "funct3": "110", "funct7": "0000000"},
    "addi":{"format": "I", "opcode": "0010011", "funct3": "000"},
    "lw":  {"format": "I", "opcode": "0000011", "funct3": "010"},
    "sw":  {"format": "S", "opcode": "0100011", "funct3": "010"},
    "beq": {"format": "B", "opcode": "1100011", "funct3": "000"},
    "bne": {"format": "B", "opcode": "1100011", "funct3": "001"},
    "jal": {"format": "J", "opcode": "1101111"}
}

# Assembler direktifleri: komut üretmeyen, sadece derleyiciye yönelik özel anahtar kelimeler
directives = {".text", ".data", ".word", ".byte", ".end"}


# Her komutun beklediği operand (argüman) sayısı.
# -1: değişken sayıda operand kabul eder (ör: .word, .byte)
operand_counts = {
    "add": 3, "sub": 3, "addi": 3, "and": 3, "or": 3,
    "lw": 2, "sw": 2, "beq": 3, "bne": 3, "jal": 2,
    ".text": 0, ".data": 0, ".end": 0, ".word": -1, ".byte": -1
}

def validate_and_get_reg(reg_str):
    """Verilen register ismini doğrular ve 5-bit ikili gösterimini döndürür.
    Geçerli format: x0 - x31
    """
    # Register isminin 'x' ile başlayıp başlamadığını kontrol et
    if not reg_str.startswith('x'):
        raise ValueError(f"Register '{reg_str}' hatalı. 'x' ile başlamalı (ör: x1).")
    try:
        num = int(reg_str[1:])  # 'x' sonrasındaki sayıyı al
        # Register numarasının geçerli aralıkta olup olmadığını kontrol et
        if num < 0 or num > 31:
            raise ValueError(f"Register '{reg_str}' sınırların dışında. (0-31 aralığında olmalı)")
        return format(num, '05b')  # 5 haneli ikili formata çevir
    except ValueError as e:
        if "invalid literal" in str(e):
            raise ValueError(f"'{reg_str}' geçerli bir register formatı değil.")
        raise e

def validate_and_get_imm(imm_str, bits):
    """Verilen anlık değeri (immediate) doğrular ve 'bits' uzunluğunda ikili gösterimini döndürür.
    int(..., 0) kullanımı sayesinde hex (0x), oktal (0o) ve onluk sayıları otomatik tanır.
    """
    try:
        imm_int = int(imm_str, 0)  # Onluk, hexadecimal (0x...) gibi farklı tabanları destekler
        # İşaretli tam sayı için izin verilen minimum ve maksimum değerleri hesapla
        min_val = -(1 << (bits - 1))
        max_val = (1 << (bits - 1)) - 1
        if imm_int < min_val or imm_int > max_val:
            raise ValueError(f"Değer '{imm_str}' {bits}-bit sınırlarına sığmıyor ({min_val} ile {max_val} arası).")
        
        # Negatif sayılar için ikiye tümleme (two's complement) gösterimini hesapla
        if imm_int < 0:
            imm_int = (1 << bits) + imm_int
        return format(imm_int, f'0{bits}b')  # Başa sıfır eklenmiş ikili string döndür
    except ValueError as e:
        if "invalid literal" in str(e):
            raise ValueError(f"'{imm_str}' geçerli bir sayı değil.")
        raise e

def validate_and_get_byte(byte_str):
    """.byte için değeri doğrular ve 8-bit ikili gösterimini döndürür.
    Kabul edilen aralık: -128..255 (hem işaretli hem işaretsiz yazım desteklenir).
    """
    try:
        byte_int = int(byte_str, 0)
        if byte_int < -128 or byte_int > 255:
            raise ValueError(f"Değer '{byte_str}' 8-bit sınırlarına sığmıyor (-128 ile 255 arası).")

        # Negatifler two's complement ile, pozitifler doğrudan 8-bit'e çevrilir.
        if byte_int < 0:
            byte_int = (1 << 8) + byte_int
        return format(byte_int, '08b')
    except ValueError as e:
        if "invalid literal" in str(e):
            raise ValueError(f"'{byte_str}' geçerli bir sayı değil.")
        raise e

class PicoRVAssembler:
    """İki geçişli (two-pass) RISC-V assembler sınıfı.
    1. Geçiş (pass_one): Etiketleri (label) tespit eder, sembol tablosunu oluşturur.
    2. Geçiş (pass_two): Makine kodunu üretir, etiket referanslarını çözer.
    """

    def __init__(self):
        self.symbol_table = {}   # Etiket adı -> adres eşlemesini tutar
        self.machine_code = []   # Üretilen makine kodu satırlarını tutar
        self.errors = []         # Derleme sırasında oluşan hata mesajlarını tutar
        
        # Bellek bölümlerinin başlangıç adresleri
        self.TEXT_BASE = 0x00000000  # Kod (instruction) bölümünün başlangıç adresi
        self.DATA_BASE = 0x20000000  # Veri bölümünün başlangıç adresi
        self.text_pc = self.TEXT_BASE  # Anlık .text program sayacı
        self.data_pc = self.DATA_BASE  # Anlık .data program sayacı
        self.current_section = ".text"  # Şu an işlenen bölüm (.text veya .data)

    def parse_line(self, line):
        """Tek bir satırı ayrıştırır; yorum kısmını atar, etiketi ve token listesini döndürür."""
        # '#' karakterinden itibaren yorum satırını kaldır
        line = line.split('#')[0].strip()
        if not line:  # Boş satırı atla
            return None, []
        
        # Satırda ':' varsa sol taraf etikettir
        label = None
        if ':' in line:
            parts = line.split(':', 1)  # Yalnızca ilk ':' üzerinden böl
            label = parts[0].strip()
            line = parts[1].strip()  # Etiket sonrasındaki kısmı işlemeye devam et
            
        # Virgül ve boşluklara göre tokenize et, boş elemanları filtrele
        tokens = [t.strip() for t in re.split(r'[,\s]+', line) if t.strip()]
        return label, tokens

    def pass_one(self, source_code):
        """Birinci geçiş: Kaynak kodu tarar, tüm etiketleri bulur ve
        sembol tablosuna adres bilgisiyle kaydeder.
        Bu aşamada makine kodu üretilmez.
        """
        # Program sayaçlarını ve durumu sıfırla
        self.text_pc = self.TEXT_BASE
        self.data_pc = self.DATA_BASE
        self.current_section = ".text"
        self.symbol_table.clear()
        
        for i, line in enumerate(source_code):
            line_num = i + 1
            try:
                label, tokens = self.parse_line(line)
                
                # Bölüm direktifine göre aktif bölümü güncelle
                if tokens and tokens[0] in [".text", ".data"]:
                    self.current_section = tokens[0]
                
                if label:
                    # Aynı etiket iki kez tanımlanıyorsa hata ver
                    if label in self.symbol_table:
                        self.errors.append(f"Satır {line_num}: '{label}' etiketi zaten tanımlanmış.")
                    else:
                        # Etiketi bulunduğu bölümün mevcut PC değeriyle kaydet
                        if self.current_section == ".text":
                            self.symbol_table[label] = self.text_pc
                        else:
                            self.symbol_table[label] = self.data_pc
                        
                if tokens:
                    instruction = tokens[0]
                    if instruction in opcode_table:
                        # Komutlar yalnızca .text bölümünde olabilir
                        if self.current_section != ".text":
                            self.errors.append(f"Satır {line_num}: Kodlar (instructions) sadece .text bölümünde olmalıdır.")
                        self.text_pc += 4  # Her RISC-V komutu 4 byte yer kaplar
                    elif instruction == ".word":  # 32-bit (4 byte) veri
                        self.data_pc += 4 * (len(tokens) - 1)
                    elif instruction == ".byte":  # 8-bit (1 byte) veri
                        self.data_pc += 1 * (len(tokens) - 1)
                    elif instruction not in directives:
                        self.errors.append(f"Satır {line_num}: Bilinmeyen komut veya direktif '{instruction}'")
            except Exception as e:
                self.errors.append(f"Satır {line_num}: Beklenmeyen hata - {str(e)}")

    def pass_two(self, source_code):
        """İkinci geçiş: Sembol tablosu hazır olduğundan etiket referansları
        çözülür ve her komut için makine kodu üretilir.
        """
        # Program sayaçlarını yeniden başlat
        self.text_pc = self.TEXT_BASE
        self.data_pc = self.DATA_BASE
        self.current_section = ".text"
        self.machine_code.clear()
        
        for i, line in enumerate(source_code):
            line_num = i + 1
            label, tokens = self.parse_line(line)
            
            # Boş satır veya yalnızca etiket içeren satırı atla
            if not tokens:
                continue
                
            instruction = tokens[0]
            
            # Bölüm direktiflerini işle, PC'yi değiştirme
            if instruction in [".text", ".data"]:
                self.current_section = instruction
                continue
                
            # .end ve .org direktifleri bu assembler'da işlenmez, atla
            if instruction in [".end", ".org"]:
                continue
                
            # .word direktifi: her değer için 4 byte veri üret
            if instruction == ".word":
                for val in tokens[1:]:
                    try:
                        bin_val = validate_and_get_imm(val, 32)
                        hex_val = hex(int(bin_val, 2))[2:].zfill(8).upper()
                        self.machine_code.append(f"0x{self.data_pc:08X}:\t0x{hex_val}")
                        self.data_pc += 4  # Sonraki .word için data PC'yi 4 artır
                    except Exception as e:
                        self.errors.append(f"Satır {line_num}: .word hatası - {str(e)}")
                continue

            # .byte direktifi: her değer için 1 byte veri üret
            if instruction == ".byte":
                for val in tokens[1:]:
                    try:
                        bin_val = validate_and_get_byte(val)
                        hex_val = hex(int(bin_val, 2))[2:].zfill(2).upper()
                        self.machine_code.append(f"0x{self.data_pc:08X}:\t0x{hex_val}")
                        self.data_pc += 1  # Sonraki .byte için data PC'yi 1 artır
                    except Exception as e:
                        self.errors.append(f"Satır {line_num}: .byte hatası - {str(e)}")
                continue
                
            if instruction in opcode_table:
                # Operand sayısını doğrula (-1 ise değişken sayıda operand kabul edilir)
                expected_args = operand_counts.get(instruction, -1)
                actual_args = len(tokens) - 1
                if expected_args != -1 and actual_args != expected_args:
                    self.errors.append(f"Satır {line_num}: '{instruction}' komutu {expected_args} argüman bekler, {actual_args} verildi.")
                    continue

                fmt = opcode_table[instruction]["format"]  # Komut formatını al (R, I, S, B, J)
                args = tokens[1:]  # Komut adının dışındaki argümanları al
                
                try:
                    # Makine kodunu üret ve hexadecimal formatında çıktı listesine ekle
                    m_code = self.generate_machine_code(instruction, fmt, args, self.text_pc)
                    hex_code = hex(int(m_code, 2))[2:].zfill(8).upper()
                    self.machine_code.append(f"0x{self.text_pc:08X}:\t0x{hex_code}")
                except Exception as e:
                    self.errors.append(f"Satır {line_num}: {str(e)}")
                    
                self.text_pc += 4  # Bir sonraki komut için PC'yi 4 artır

    def generate_machine_code(self, inst, fmt, args, current_pc):
        """Komut formatına (R/I/S/B/J) göre 32-bit ikili makine kodunu üretir.
        RISC-V komut kodlama kurallarına uygun bit dizisi döndürür.
        """
        op = opcode_table[inst]  # Komutun opcode/funct bilgilerini al
        
        if fmt == "R":
            # R-format: funct7 | rs2 | rs1 | funct3 | rd | opcode
            # Örnek: add x1, x2, x3  ->  rd=x1, rs1=x2, rs2=x3
            rd, rs1, rs2 = validate_and_get_reg(args[0]), validate_and_get_reg(args[1]), validate_and_get_reg(args[2])
            return f"{op['funct7']}{rs2}{rs1}{op['funct3']}{rd}{op['opcode']}"
            
        elif fmt == "I":
            # I-format: imm[11:0] | rs1 | funct3 | rd | opcode
            # lw komutu için  imm(rs1) söz dizimini ayrıca işle
            if inst == "lw":
                rd = validate_and_get_reg(args[0])
                # offset(register) biçimini regex ile ayrıştır
                match = re.match(r'^(-?(?:0x[0-9a-fA-F]+|\d+))\((x\d+)\)$', args[1])
                if not match:
                    raise ValueError(f"Bellek adresi formatı hatalı: '{args[1]}'. Doğru format: imm(reg)")
                imm = validate_and_get_imm(match.group(1), 12)   # 12-bit ofset
                rs1 = validate_and_get_reg(match.group(2))        # Taban register
            else:
                # addi gibi standart I-format komutları: rd, rs1, imm
                rd, rs1 = validate_and_get_reg(args[0]), validate_and_get_reg(args[1])
                imm = validate_and_get_imm(args[2], 12)
            return f"{imm}{rs1}{op['funct3']}{rd}{op['opcode']}"
            
        elif fmt == "S":
            # S-format: imm[11:5] | rs2 | rs1 | funct3 | imm[4:0] | opcode
            # Anlık değer (immediate) ikiye bölünür ve ayrı ayrı yerleştirilir
            rs2 = validate_and_get_reg(args[0])  # Kaydedilecek veri kaynağı
            match = re.match(r'^(-?(?:0x[0-9a-fA-F]+|\d+))\((x\d+)\)$', args[1])
            if not match:
                raise ValueError(f"Bellek adresi formatı hatalı: '{args[1]}'. Doğru format: imm(reg)")
            imm_val = validate_and_get_imm(match.group(1), 12)
            rs1 = validate_and_get_reg(match.group(2))  # Taban adres register'ı
            # imm bitlerini RISC-V S-format kurallarına göre bölerek yerleştir
            return f"{imm_val[0:7]}{rs2}{rs1}{op['funct3']}{imm_val[7:12]}{op['opcode']}"
            
        elif fmt == "B":
            # B-format (dal): imm[12|10:5] | rs2 | rs1 | funct3 | imm[4:1|11] | opcode
            # Ofset, hedef etiketin adresi ile mevcut PC arasındaki farktır
            rs1, rs2 = validate_and_get_reg(args[0]), validate_and_get_reg(args[1])
            target_label = args[2]
            if target_label not in self.symbol_table:
                raise ValueError(f"'{target_label}' etiketi (label) bulunamadı.")
            target_addr = self.symbol_table[target_label]
            offset = target_addr - current_pc  # PC-relative ofset
            
            # RISC-V komutları 2-byte hizalı olmak zorunda, tek sayılı ofset geçersiz
            if offset % 2 != 0:
                raise ValueError(f"Atlama adresi 2'nin katı olmalı (Misaligned branch offset: {offset})")
                
            imm_bin = validate_and_get_imm(str(offset), 13)  # 13-bit işaretli ofset
            # RISC-V B-format bit sıralaması: [12][10:5] ... [4:1][11]
            return f"{imm_bin[0]}{imm_bin[2:8]}{rs2}{rs1}{op['funct3']}{imm_bin[8:12]}{imm_bin[1]}{op['opcode']}"
            
        elif fmt == "J":
            # J-format (koşulsuz atlama): imm[20|10:1|11|19:12] | rd | opcode
            # jal komutu: rd'ye dönüş adresini (PC+4) yazar ve hedefe atlar
            rd = validate_and_get_reg(args[0])  # Dönüş adresi kaydedilecek register
            target_label = args[1]
            if target_label not in self.symbol_table:
                raise ValueError(f"'{target_label}' etiketi (label) bulunamadı.")
            target_addr = self.symbol_table[target_label]
            offset = target_addr - current_pc  # PC-relative ofset
            
            # RISC-V komutları 2-byte hizalı olmalı
            if offset % 2 != 0:
                raise ValueError(f"Atlama adresi 2'nin katı olmalı (Misaligned jump offset: {offset})")
                
            imm_bin = validate_and_get_imm(str(offset), 21)  # 21-bit işaretli ofset
            # RISC-V J-format bit sıralaması: [20][10:1][11][19:12]
            return f"{imm_bin[0]}{imm_bin[10:20]}{imm_bin[9]}{imm_bin[1:9]}{rd}{op['opcode']}"

    def assemble(self, source_code):
        """Derleme işlemini başlatır. Önce pass_one ile sembol tablosunu oluşturur,
        hata yoksa pass_two ile makine kodunu üretir.
        Döndürür: (machine_code listesi, symbol_table sözlüğü, errors listesi)
        """
        self.errors = []
        self.pass_one(source_code)   # 1. Geçiş: etiket tespiti
        if not self.errors:           # Yalnızca 1. geçiş hatasızsa 2. geçişe geç
            self.pass_two(source_code)  # 2. Geçiş: kod üretimi
        return self.machine_code, self.symbol_table, self.errors