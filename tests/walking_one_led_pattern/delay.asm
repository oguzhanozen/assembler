.text

.global delay_start

.extern loop

delay_start:
    addi x7, x7, -1
    bne  x7, x0, delay_start

    slli x6, x6, 1          # Shift the LED pattern left
    addi x8, x0, 64         # Restart after all six LEDs are visited
    bne  x6, x8, loop       # loop is defined in another object

    addi x6, x0, 1
    jal  x0, loop           # Return to the external loop symbol
