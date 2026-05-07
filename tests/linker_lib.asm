# Successful linker demo: provides helper and shared_value for linker_main.asm
.global helper
.global shared_value

.text
helper:
    add x10, x1, x2
    addi x11, x10, 1
    jalr x0, x5, 0

.data
shared_value:
    .word 1234
message:
    .byte 79, 75, 10, 0
.end
