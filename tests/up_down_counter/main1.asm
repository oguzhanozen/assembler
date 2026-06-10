.text
.global _start
.global save_and_show
.extern increment_count
.extern decrement_count

_start:
    lui  x6, 0x10000
    addi x7, x6, 4            # button state address

    addi x9, x0, 0               # led state adress
    sw   x9, 0(x6)

input_wait:
    lw   x11, 0(x7)

    andi x13, x11, 1
    bne  x13, x0, increment_count

    andi x14, x11, 2
    bne  x14, x0, decrement_count

    jal  x0, input_wait

save_and_show:
    sw   x9, 0(x6)

debounce_wait:
    lw   x11, 0(x7)
    andi x11, x11, 3
    bne  x11, x0, debounce_wait
    jal  x0, input_wait
.end
