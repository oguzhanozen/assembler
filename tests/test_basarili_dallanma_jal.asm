# Test 3: Label, beq/bne ve jal akisi (basarili)
.text
main:
    addi x1, x0, 3
    addi x2, x0, 0
loop:
    addi x2, x2, 1
    addi x1, x1, -1
    bne x1, x0, loop
    beq x2, x0, fail
    jal x0, done
fail:
    addi x3, x0, 255
    sw x3, 0(x0)
done:
    addi x4, x0, 1
.end
