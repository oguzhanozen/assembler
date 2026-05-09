# PicoRV32I Assembler IDE

Bu proje, egitim amacli gelistirilmis iki gecisli (two-pass) bir RISC-V RV32I assembler ve Tkinter tabanli bir GUI uygulamasidir.

## Proje Ozeti

- Kaynak kodu iki adimda derler:
  - Pass 1: Label/symbol table olusturur.
  - Pass 2: Makine kodunu uretir.
- GUI uzerinden assembly kodunu cevirir, hata/symbol/object code sonucunu gosterir.
- GUI uzerinden .asm dosyasi yukleme ve editor icerigini .asm olarak kaydetme destegi sunar.
- Basarili derlemede object code cikisini .o uzantisiyla, aktif .asm dosya adiyla uyumlu sekilde kaydeder.
- Linker, birden fazla JSON tabanli .o dosyasini tek bellek imajina baglar ve HEX/JSON cikti uretir.

## Desteklenen Komutlar

- R-tipi: add, sub, and, or, xor, sll, srl, sra
- I-tipi: addi, lw, lh, lbu, jalr
- S-tipi: sw, sh, sb
- B-tipi: beq, bne, blt, bge
- J-tipi: jal
- U-tipi: lui, auipc
- Sistem: ecall, ebreak

## Desteklenen Direktifler

- .text
- .data
- .word
- .byte
- .end
- .global
- .extern

## Immediate ve Veri Kurallari

- Komut immediate degerleri ilgili bit-genisliginde isaretli aralikta dogrulanir.
  - addi/lw/sw offset: 12-bit isaretli aralik
  - beq/bne: 13-bit branch offset
  - jal: 21-bit jump offset
  - lui/auipc: 20-bit U-type immediate alani dogrudan yazilir. Ornek: `lui x5, 1` register etkisi olarak `1 << 12` yukler.
- .word: 32-bit isaretli deger kabul eder.
- .byte: -128 ile 255 araligini kabul eder.
  - 0..255 degerleri 8-bit olarak yazilir.
  - Negatif degerler two's complement olarak kodlanir.

## Proje Yapisi

```text
assembler/
  main.py
  README.md
  big_o_grafik.png
  src/
    __init__.py
    assembler.py
    gui.py
    linker.py
  outputs/
    <asm_dosya_adi>.o
    program.hex
    program.linked.json
```

## Gereksinimler

- Python 3.9+
- Harici kutuphane gerektirmez (yalnizca standart kutuphane)

## Calistirma

Proje kok klasorunde:

```bash
python main.py
```

GUI kullanim adimlari:

1. Sol editor alanina assembly kodunu girin.
2. Isterseniz .asm Yukle ile disaridan bir .asm dosyasi acin.
3. Isterseniz .asm Kaydet ile editor icerigini .asm olarak kaydedin.
4. Kodu Cevir (Assemble) butonuna basin.
5. Sag panelde hata, symbol table ve object code ciktilarini inceleyin.
6. Basarili derlemede dosyalar otomatik olarak outputs klasorune yazilir:
  - outputs/<asm_dosya_adi>.o
7. Linker > Object Dosyalarini Linkle... menusuyle birden fazla .o dosyasini secip linkleyin.

Komut satirindan linker kullanimi:

```bash
python -m src.linker outputs/modul1.o outputs/modul2.o -o outputs/program
```

Bu komut iki cikti uretir:

- outputs/program.hex
- outputs/program.linked.json

## Cikti Formati

- Assembler .o dosyasi JSON formatindadir:
  - text: 32-bit instruction word listesi
  - data: 1-byte veya 4-byte veri entry listesi
  - symbols: section, offset, visibility bilgileri
  - relocations: section, offset, type, symbol bilgileri
- Linker HEX dosyasi BRAM icin 32-bit word-per-line formatindadir.
- Linker JSON dosyasi layout, final text/data, global symbol table ve uygulanan relocation kayitlarini icerir.

## Bilinen Sinirlar

- Tam GNU assembler/linker uyumlulugu hedeflenmemistir.
- ELF uretilmiyor; proje icin JSON executable ve HEX bellek imaji uretilir.
- Linker script mantigi v1'de sabittir: .text 0x00000000, .data text bitiminden sonra 4-byte hizali baslar.
