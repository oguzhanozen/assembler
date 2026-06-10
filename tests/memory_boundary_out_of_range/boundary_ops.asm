.text
.global safe_boundary_write
.global overflow_forced_write
.extern debounce_loop

safe_boundary_write:
    lui  x13, 4
    addi x13, x13, -4
    sw   x10, 0(x13)
    addi x14, x0, 1
    sw   x14, 0(x6)
    jal  x0, debounce_loop

overflow_forced_write:
    lui  x13, 1
    slli x13, x13, 4
    sw   x10, 0(x13)
    addi x14, x0, 0x3F
    sw   x14, 0(x6)
    jal  x0, debounce_loop