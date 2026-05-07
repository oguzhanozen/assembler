# Test 1: Temel aritmetik ve mantik komutlari (basarili)
.text
main:
    addi x1, x0, 10
    addi x2, x0, 3
    add x3, x1, x2
    sub x4, x1, x2
    and x5, x1, x2
    or x6, x1, x2
    sw x3, 0(x0)
    sw x4, 4(x0)
    sw x5, 8(x0)
    sw x6, 12(x0)
.end
