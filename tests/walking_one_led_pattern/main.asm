.text

.global _start
.global loop

.extern delay_start

_start:
    lui  x5, 0x10000        # x5 = 0x10000000, LED address
    addi x6, x0, 1          # x6 = LED pattern

loop:
    sw   x6, 0(x5)          # Write pattern to LEDs

    lui  x7, 0x01000        # Initialize delay counter
    jal  x0, delay_start    # delay_start is defined in another object
