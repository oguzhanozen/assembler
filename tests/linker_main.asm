# Successful linker demo: main object references symbols from linker_lib.asm
.global main
.extern helper
.extern shared_value

.text
main:
    addi x1, x0, 5
    addi x2, x0, 3
    jal x5, helper
    lw x6, shared_value(x0)
    sw x6, shared_value(x0)
    bne x1, x2, done
    addi x7, x0, 0
done:
    jal x0, done

.data
main_value:
    .word 42
    .byte 1, 2, 3, 4
.end
