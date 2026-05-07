# Test: Immediate degerleri (basarili)
.text
main:
    # 12-bit immediate sinirlari: -2048 ile 2047
    addi x1, x0, 2047
    addi x2, x0, -2048

    # Bellek offset immediate (S ve I format)
    sw x1, 0(x0)
    sw x2, 4(x0)
    lw x3, 0(x0)
    lw x4, 4(x0)
.end
