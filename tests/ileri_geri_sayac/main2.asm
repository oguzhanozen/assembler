.init
.text
.global _start
.extern led_reg            # Harici adresten çözülecek semboller
.extern s1_reg             #
.extern s2_reg             #
.extern counter_bss        # Harici .bss alanındaki sayaç

_start:
    lui  x5, %hi(led_reg)
    lw   x6, %lo(led_reg)(x5)        # x6 = LED adresi
    lui  x5, %hi(s1_reg)
    lw   x7, %lo(s1_reg)(x5)         # x7 = S1 adresi
    lui  x5, %hi(s2_reg)
    lw   x8, %lo(s2_reg)(x5)         # x8 = S2 adresi

    # Harici .bss segmentinde ayrılan sayacın RAM adresini çöz ve sıfırla
    lui  x5, %hi(counter_bss)
    addi x9, x5, %lo(counter_bss)    # x9 = Sayaç RAM adresi
    addi x10, x0, 0
    sw   x10, 0(x9)                  # counter_bss = 0

input_wait:
    lw   x11, 0(x7)                  # S1 butonunu oku
    andi x11, x11, 1
    bne  x11, x0, increment_count

    lw   x12, 0(x8)                  # S2 butonunu oku
    andi x12, x12, 2
    bne  x12, x0, decrement_count

    jal  x0, input_wait

increment_count:
    lw   x13, 0(x9)                  # Sayacı RAM'den oku
    addi x13, x13, 1                 # i++
    addi x14, x0, 64                 # Üst sınır kontrolü
    blt  x13, x14, save_and_show
    addi x13, x0, 0
    jal  x0, save_and_show

decrement_count:
    lw   x13, 0(x9)                  # Sayacı RAM'den oku
    addi x13, x13, -1                # i--
    bge  x13, x0, save_and_show      # Alt sınır kontrolü
    addi x13, x0, 63                 # Başa sar

save_and_show:
    sw   x13, 0(x9)                  # Güncellenen sayacı RAM'e geri yaz
    sw   x13, 0(x6)                  # Sayaç değerini doğrudan LED bit deseni olarak yaz

debounce_wait:
    lw   x11, 0(x7)
    andi x11, x11, 1
    lw   x12, 0(x8)
    andi x12, x12, 2
    or   x14, x11, x12
    bne  x14, x0, debounce_wait      # İki buton da bırakılana kadar bekle
    jal  x0, input_wait
.end
