.text
.global _start
.global debounce_loop
.extern safe_boundary_write
.extern overflow_forced_write

_start:
    lui  x6, 0x10000
    addi x7, x6, 4
    addi x10, x0, 0xAA

main_check:
    lw   x11, 0(x7)
    andi x11, x11, 1
    bne  x11, x0, safe_boundary_write

    lw   x12, 0(x7)
    andi x12, x12, 2
    bne  x12, x0, overflow_forced_write

    jal  x0, main_check

    debounce_loop:
    lw   x11, 0(x7)
    andi x11, x11, 3
    bne  x11, x0, debounce_loop
    jal  x0, main_check
.end