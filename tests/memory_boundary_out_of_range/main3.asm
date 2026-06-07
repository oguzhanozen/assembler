.init
.text
.global _start
.extern led_ptr            # Harici adresten çözülecek simgeler
.extern s1_ptr
.extern s2_ptr
.extern test_pattern       # Harici dosyada tanımlı güvenli veri bloku

_start:
    lui  x5, %hi(led_ptr)
    lw   x6, %lo(led_ptr)(x5)        # x6 = LED adresi
    lui  x5, %hi(s1_ptr)
    lw   x7, %lo(s1_ptr)(x5)         # x7 = S1 adresi
    lui  x5, %hi(s2_ptr)
    lw   x8, %lo(s2_ptr)(x5)         # x8 = S2 adresi

    # Harici dosyadan test verisini yükle (Linker Relocation Testi)
    lui  x5, %hi(test_pattern)
    lw   x10, %lo(test_pattern)(x5)  # x10 = 0x000000AA

main_check:
    lw   x11, 0(x7)                  # S1 butonunu oku
    andi x11, x11, 1
    bne  x11, x0, safe_boundary_write # S1 (bit 0) basıldıysa güvenli sınıra yaz

    lw   x12, 0(x8)                  # S2 butonunu oku
    andi x12, x12, 2
    bne  x12, x0, overflow_forced_write # S2 (bit 1) basıldıysa taşmayı tetikle

    jal  x0, main_check

safe_boundary_write:
    # 16 KiB BRAM'in son geçerli kelime adresi: 0x00003FFC
    lui  x13, 4                      # x13 = 0x00004000
    addi x13, x13, -4                # x13 = 0x00003FFC (Tam Sınır)

    sw   x10, 0(x13)                 # Sınır içine başarıyla yaz

    addi x14, x0, 1                  # Başarılı kodu: 0x01
    sw   x14, 0(x6)                  # Sadece LED0'ı yak (Hata yok)
    jal  x0, debounce_loop

overflow_forced_write:
    # 16 KiB BRAM Sınırının tam dışı (Taşma Alanı): 0x00004000
    lui  x13, 1
    slli x13, x13, 4                 # x13 = 0x00004000 (Sınır ihlali!)

    sw   x10, 0(x13)                 # Donanımsal sınırı zorla (Yazma hatası tetikle)

    addi x14, x0, 0x3F               # Hata/Taşma Kodu: 0x3F (Tüm LED'ler)
    sw   x14, 0(x6)                  # Tüm LED'leri yakarak hata uyarısı ver

debounce_loop:
    lw   x11, 0(x7)
    andi x11, x11, 1
    lw   x12, 0(x8)
    andi x12, x12, 2
    or   x14, x11, x12
    bne  x14, x0, debounce_loop      # İki buton da bırakılana kadar bekle
    jal  x0, main_check
.end
