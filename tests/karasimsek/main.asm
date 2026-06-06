.text

.global _start
.global loop

.extern delay_start

_start:
    lui  x5, 0x10000        # x5 = 0x10000000, LED adresi
    addi x6, x0, 1          # x6 = LED deseni

loop:
    sw   x6, 0(x5)          # LED'e yaz

    lui  x7, 0x01000        # gecikme sayacı
    jal  x0, delay_start    # delay_start başka dosyada
