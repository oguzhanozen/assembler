# PicoRV32I Assembler, Linker Script Linker ve IDE

Bu proje eğitim amaçlı bir RISC-V RV32I assembler, JSON tabanlı object linker ve Tkinter IDE uygulamasıdır.

Assembler kaynak dosyalarını adres bağımsız V2 object dosyalarına dönüştürür. Nihai bellek yerleşimi assembler tarafından değil, zorunlu GNU-benzeri linker script tarafından belirlenir. Linker, UART loader için tek adresli `.picoimg` dosyası, her `MEMORY` bölgesi için ayrı BRAM uyumlu HEX görüntüsü ve ayrıntılı `.linked.json` raporu üretir.

## Temel Akış

1. Her `.asm` dosyasını ayrı ayrı assemble ederek V2 `.o` dosyası üretin.
2. FPGA bellek haritasını bir `.ld` linker script içinde tanımlayın.
3. Object dosyalarını linker script ile linkleyin.
4. UART loader ile çalışırken `.picoimg` dosyasını gönderin; doğrudan BRAM başlangıç içeriği gerektiğinde bölge bazlı HEX dosyalarını kullanın.

Assembler aşaması artık HEX üretmez. Bir section'ın nihai adresi link aşamasından önce bilinmediği için adreslenmiş HEX yalnız linker tarafından oluşturulur.

## Desteklenen Assembly Section ve Direktifleri

Standart section kısa yolları:

```asm
.init
.text
.rodata
.data
.bss
```

Adlandırılmış section:

```asm
.section .vectors, "ax", @progbits
.section .scratch, "aw", @nobits
```

Özel section isimlerinde flags ve tip zorunludur:

- `a`: allocatable/read-only veri
- `w`: writable
- `x`: executable
- `@progbits`: object içinde byte içeriği taşır
- `@nobits`: yalnız çalışma zamanı boyutu taşır; HEX'e yazılmaz

Veri ve yerleşim direktifleri:

- `.word`, `.byte`
- `.zero N`, `.space N`
- `.align N`: pozitif power-of-two byte hizalaması
- `.global`, `.extern`, `.end`

Desteklenen komutlar:

- R: `add`, `sub`, `and`, `or`, `xor`, `sll`, `srl`, `sra`
- I: `addi`, `slli`, `lw`, `lh`, `lbu`, `jalr`
- S: `sw`, `sh`, `sb`
- B: `beq`, `bne`, `blt`, `bge`
- J/U: `jal`, `lui`, `auipc`
- Sistem: `ecall`, `ebreak`

## V2 Object Formatı

Assembler yalnız V2 object üretir:

```json
{
  "format": "picorv-json-object",
  "version": 2,
  "sections": [],
  "symbols": {},
  "relocations": []
}
```

Her section `name`, `type`, `flags`, `alignment`, `size` ve PROGBITS için byte tabanlı `data` alanlarını taşır. Symbol ve relocation offset'leri section-relative byte offset'tir.

Linker eski V1 `text`/`data` object dosyalarını okumaya devam eder.

## Linker Script

Linker script her link işleminde zorunludur. Desteklenen GNU-benzeri alt küme:

- `ENTRY(symbol)`
- `MEMORY`
- `SECTIONS`
- `ORIGIN`, `LENGTH`, `ALIGN`
- Hex/decimal sayılar, `K`/`M`, `+`, `-`, location counter `.`
- `*(.text*)` ve `startup.o(.init)` seçicileri
- `(NOLOAD)` ve `> REGION`

Örnek tek BRAM düzeni:

```ld
ENTRY(_start);

MEMORY {
    BRAM (rwx) : ORIGIN = 0x00000000, LENGTH = 16K;
}

SECTIONS {
    .init   : ALIGN(4) { *(.init*) }   > BRAM
    .text   : ALIGN(4) { *(.text*) }   > BRAM
    .rodata : ALIGN(4) { *(.rodata*) } > BRAM
    .data   : ALIGN(4) { *(.data*) }   > BRAM
    .bss (NOLOAD) : ALIGN(4) { *(.bss*) } > BRAM
}
```

Hazır scriptler:

- `examples/single_bram.ld`: kod ve veriyi tek BRAM içinde yerleştirir.
- `examples/split_rom_ram.ld`: kodu ROM, veri ve `.bss` alanını RAM içine yerleştirir.

Script hiçbir input section'ı eşleştirmeden bırakamaz. Orphan section, region overflow/çakışması, region flag uyumsuzluğu ve global olmayan/eksik entry link hatasıdır.

## Komut Satırı

Link:

```bash
python -m src.linker outputs/assembler/main.o outputs/assembler/delay.o \
  -T examples/single_bram.ld \
  -o outputs/linker/program
```

Üretilen dosyalar:

- `outputs/loader/program.picoimg`
- `outputs/linker/program.linked.json`
- `outputs/linker/program.BRAM.hex`

Split ROM/RAM script kullanılırsa yüklenebilir veri bulunan her bölge için ayrı dosya üretilir:

- `outputs/linker/program.ROM.hex`
- `outputs/linker/program.RAM.hex`

Yalnız NOBITS içeren bir bölge için HEX oluşturulmaz.

## Loader Image Formatı

`.picoimg`, loader'ın ihtiyaç duyduğu program verisini ve hedef adresleri tek ikili dosyada taşır. Standart ham `.bin` dosyasından farklı olarak dosya şunları içerir:

- `PICOIMG` magic değeri ve format sürümü
- Program entry adresi
- Yüklenebilir segmentlerin hedef adresi, uzunluğu ve `rwx` izinleri
- Her segment için CRC32
- Segment tablosu ve tüm payload için image CRC32

JSON çıktısı sembol, relocation ve yerleşim incelemesi için; HEX çıktıları ise FPGA BRAM başlangıç içeriği için korunur. Bir loader image dosyasını doğrulamak ve içeriğini listelemek için:

```bash
python -m src.loader_image outputs/loader/program.picoimg
```

Tüm çok baytlı alanlar little-endian kodlanır. V1 ikili yerleşimi:

```text
Header (32 byte)
  magic[8] = "PICOIMG\0"
  version:u16, header_size:u16
  entry:u32, segment_count:u32, descriptor_size:u32
  payload_size:u32, image_crc32:u32

Segment descriptor (her segment için 16 byte)
  address:u32, length:u32, flags:u32, data_crc32:u32

Payload
  Segment verileri descriptor sırasıyla art arda
```

`image_crc32`, segment descriptor tablosu ve payload'ın tamamı üzerinden hesaplanır. `flags` alanında `r=1`, `w=2`, `x=4` bitleri kullanılır.

## UART Host Loader

Host loader `.picoimg` dosyasını doğrular, yüklenebilir segmentleri adresli UART paketlerine böler ve FPGA loader'dan her paket için ACK bekler.

```bash
python -m pip install -r requirements.txt
python -m src.host_loader --list-ports
python -m src.host_loader outputs/loader/program.picoimg --port COM5
```

Fiziksel bağlantı olmadan image ve üretilecek paket sayısını doğrulamak için:

```bash
python -m src.host_loader outputs/loader/program.picoimg --dry-run
```

Varsayılan bağlantı `115200 baud`, `8N1`, 1 saniye timeout ve paket başına 3 denemedir.

### UART Paket Protokolü V1

Tüm çok baytlı alanlar little-endian kodlanır. Her paket:

```text
Header (12 byte)
  magic[2] = A5 5A
  version:u8 = 1
  type:u8
  sequence:u8
  flags:u8
  payload_length:u16
  address:u32

Payload (0..128 byte)
CRC32:u32
```

Paket CRC32 değeri header ve payload üzerinden hesaplanır. Komutlar:

| Type | Ad | Kullanım |
|---:|---|---|
| `0x01` | `PING` | FPGA loader bağlantısını doğrular |
| `0x02` | `BEGIN` | İşlemciyi reset altında tutar ve yükleme oturumunu başlatır |
| `0x03` | `DATA` | Payload'ı `address` alanındaki hedef adrese yazar |
| `0x04` | `END` | Toplam byte sayısını ve aktarım CRC32'sini doğrular |
| `0x05` | `RUN` | İşlemciyi `address` entry değerinden çalıştırır |
| `0x80` | `ACK` | İlgili sequence numaralı komut kabul edildi |
| `0x81` | `NACK` | Komut reddedildi; payload ilk byte hata durumudur |

`BEGIN` payload'ı `entry:u32, total_bytes:u32, segment_count:u16, transfer_crc32:u32`; `END` payload'ı `total_bytes:u32, transfer_crc32:u32` biçimindedir. Transfer CRC32, DATA payload'larının gönderim sırasındaki birleşimi üzerinden hesaplanır.

Host yalnız doğru sequence numaralı ACK aldıktan sonra sonraki pakete geçer. Timeout, bozuk yanıt veya NACK durumunda aynı paket aynı sequence numarasıyla tekrar gönderilir. FPGA loader daha önce kabul ettiği sequence tekrar gelirse veriyi ikinci kez işlememeli ve önceki ACK'i tekrar göndermelidir.

`PING`, yeni bir host oturumunun sequence sayacını yeniden eşitlemesine izin verir. Böylece FPGA yeniden programlanmadan art arda farklı `.picoimg` dosyaları yüklenebilir.

## Tang Nano 9K FPGA Loader

`fpga/` klasörü Tang Nano 9K için PicoRV32, hazır UART RX/TX modülleri, CRC32 kontrollü loader FSM, 16 KiB BRAM ve LED MMIO entegrasyonunu içerir.

```text
.picoimg
  -> Python host loader
  -> USB-UART
  -> FPGA loader FSM
  -> 16 KiB BRAM
  -> PicoRV32
  -> LED MMIO
```

GowinEDA kaynak sırası, pin constraint dosyası, lisanslar ve kart kurulum adımları [`fpga/README.md`](fpga/README.md) içinde açıklanır. V1 FPGA hedefi tek BRAM ve `0x00000000` entry adresi kullanır.

## Uzak Veri Adresleme

Veri ayrı ve uzak bir RAM bölgesindeyse sembolün üst ve alt adres parçalarını relocation ile yükleyin:

```asm
.text
.global _start
_start:
    lui x5, shared_value
    lw  x6, shared_value(x5)

.data
shared_value:
    .word 42
```

`R_RISCV_HI20` ve `R_RISCV_LO12_I/S` relocation kayıtları gerçek script adresleri üzerinden uygulanır. Branch ve JAL hedefleri erişim aralığını aşarsa linker hata verir.

## IDE

```bash
python main.py
```

- `Kodu Çevir (Assemble)` aktif kaynak için yalnız `.o` üretir.
- `Linker > Object Dosyalarını Linkle...` önce object dosyalarını, sonra `.ld` script'i seçtirir.
- Link sonucu memory region, output section, symbol ve relocation bilgileri sağ panelde gösterilir.
- `FPGA > UART Loader...` `.picoimg` dosyasını seçilen COM port üzerinden karta yükler.

### IDE ile FPGA'ya Yükleme

1. Gowin Programmer ile `outputs/fpga/picorv_loader.fs` bitstream'ini karta yükleyin.
2. Assembly kaynaklarını IDE içinde assemble edin.
3. `Linker > Object Dosyalarını Linkle...` ile `.picoimg` üretin.
4. `FPGA > UART Loader...` penceresini açın.
5. COM portu ve `.picoimg` dosyasını seçin.
6. Önce `Bağlantıyı Test Et`, ardından `FPGA'ya Yükle ve Çalıştır` düğmesine basın.

Loader penceresi mevcut `HostLoader` API'sini arka plan thread'inde kullanır. Yükleme
sırasında IDE donmaz; ilerleme, ACK/NACK hataları ve sonuçlar işlem günlüğünde gösterilir.

## Testler

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Testler parser, V2 object üretimi, loader image, UART paket protokolü, ACK/NACK retry davranışı, iki region yerleşimi, NOBITS `.bss`, relocation, overflow/orphan hataları ve bölge bazlı HEX çıktısını doğrular.
