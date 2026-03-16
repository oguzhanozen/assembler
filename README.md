# PicoRV32I Assembler IDE

Bu proje, egitim ve dogrulama amacli gelistirilmis iki gecisli (two-pass) basit bir RISC-V RV32I assembler ve Tkinter tabanli bir arayuz icerir.

## Ozellikler

- RV32I alt kumesinden temel komutlar:
  - `add`, `sub`, `and`, `or`
  - `addi`
  - `lw`, `sw`
  - `beq`, `bne`
  - `jal`
- Desteklenen direktifler:
  - `.text`, `.data`, `.word`, `.byte`, `.end`
- Label/symbol table olusturma (pass-1)
- Makine kodu uretimi (pass-2)
- GUI uzerinden:
  - Assembly kodu girme
  - Syntax renklendirme
  - Hata gosterimi
  - Symbol table ve object code gosterimi
- Basarili derleme sonrasi otomatik dosya ciktilari:
  - `outputs/object_code.txt`
  - `outputs/symbol_table.txt`

## Proje Yapisi

```text
assembler/
  main.py
  README.md
  src/
    __init__.py
    assembler.py
    gui.py
  tests/
    test_basarili_*.asm
    test_hata_*.asm
  outputs/
    object_code.txt
    symbol_table.txt
```

## Gereksinimler

- Python 3.9+ (onerilen)
- Harici paket gerekmez (sadece standart kutuphane kullanilir)

## Calistirma

Proje kok dizininde:

```bash
python main.py
```

GUI acildiktan sonra:

1. Sol editor alanina asm kodunu yapistir.
2. `Kodu Cevir (Assemble)` butonuna bas.
3. Sag panelden hata/symbol/object code ciktisini incele.
4. Basarili ise txt ciktilari `outputs/` altina yazilir.

## Test Dosyalari

`tests/` klasorunde iki tip senaryo bulunur:

- `test_basarili_*.asm`: derleme hatasi beklenmez
- `test_hata_*.asm`: bilerek hata ureten senaryolar

Ornekler:

- `test_basarili_veri_direktifleri.asm`
- `test_basarili_immediate.asm`
- `test_hata_immediate_tasma.asm`

## Desteklenen Immediate Kurallari

- Komut immediate degerleri (ornegin `addi`, `lw/sw` offset): ilgili bit-genisliginde **isaretli** aralik kontrolu
- `.byte` direktifi: `-128..255` araligini kabul eder
  - Pozitif 0..255 degerler dogrudan 8-bit yazilir
  - Negatif degerler two's complement olarak kodlanir

## Bilinen Sinirlar

- Tam bir GNU toolchain uyumlulugu hedeflenmemistir.
- Relocation/linking, ELF uretimi gibi ileri adimlar yoktur.
- Simdilik GUI'de dosyadan asm acma ozelligi yok (metin editorune manuel giris/yapistirma)

