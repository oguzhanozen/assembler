# Test 4: .data + .word + .byte direktifleri (basarili)
.data
arr:   .word 1, 2, 3, 4
flags: .byte 0, 1, 2, 255
.text
main:
    lw x1, 0(x0)
    lw x2, 4(x0)
    add x3, x1, x2
    sw x3, 16(x0)
.end
