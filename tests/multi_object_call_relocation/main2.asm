.text
.global _start
.extern fonksiyon_topla
.extern fonksiyon_cikar

_start:
    lui  x6, 0x10000
    addi x7, x6, 4

    addi x10, x0, 12
    addi x11, x0, 4

main_loop:
    lw   x12, 0(x7)
    andi x12, x12, 1
    bne  x12, x0, call_topla

    lw   x13, 0(x7)
    andi x13, x13, 2
    bne  x13, x0, call_cikar

    addi x14, x0, 0
    sw   x14, 0(x6)
    jal  x0, main_loop

call_topla:
    jal  x1, fonksiyon_topla
    jal  x0, ekrana_bas

call_cikar:
    jal  x1, fonksiyon_cikar

ekrana_bas:
    sw   x14, 0(x6)
    jal  x0, main_loop
.end