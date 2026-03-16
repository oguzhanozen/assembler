# Test 2: Bellek okuma/yazma ve negatif offset immediate (basarili)
.text
main:
    addi x1, x0, 32
    addi x2, x0, 99
    sw x2, 0(x1)
    lw x3, 0(x1)
    addi x4, x3, -5
    sw x4, 4(x1)
.end
