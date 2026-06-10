.init
.text
.global _start
.extern led_reg            # External symbol containing the LED address
.extern s1_reg             # External symbol containing the S1 address
.extern s2_reg             # External symbol containing the S2 address
.extern counter_bss        # Counter allocated in an external .bss section

_start:
    lui  x5, %hi(led_reg)
    lw   x6, %lo(led_reg)(x5)        # x6 = LED address
    lui  x5, %hi(s1_reg)
    lw   x7, %lo(s1_reg)(x5)         # x7 = S1 address
    lui  x5, %hi(s2_reg)
    lw   x8, %lo(s2_reg)(x5)         # x8 = S2 address

    # Resolve and clear the counter allocated in the external .bss section
    lui  x5, %hi(counter_bss)
    addi x9, x5, %lo(counter_bss)    # x9 = counter RAM address
    addi x10, x0, 0
    sw   x10, 0(x9)                  # counter_bss = 0

input_wait:
    lw   x11, 0(x7)                  # Read S1
    andi x11, x11, 1
    bne  x11, x0, increment_count

    lw   x12, 0(x8)                  # Read S2
    andi x12, x12, 2
    bne  x12, x0, decrement_count

    jal  x0, input_wait

increment_count:
    lw   x13, 0(x9)                  # Read counter from RAM
    addi x13, x13, 1                 # i++
    addi x14, x0, 64                 # Check upper boundary
    blt  x13, x14, save_and_show
    addi x13, x0, 0
    jal  x0, save_and_show

decrement_count:
    lw   x13, 0(x9)                  # Read counter from RAM
    addi x13, x13, -1                # i--
    bge  x13, x0, save_and_show      # Check lower boundary
    addi x13, x0, 63                 # Wrap to maximum value

save_and_show:
    sw   x13, 0(x9)                  # Store updated counter in RAM
    sw   x13, 0(x6)                  # Display counter as an LED bit pattern

debounce_wait:
    lw   x11, 0(x7)
    andi x11, x11, 1
    lw   x12, 0(x8)
    andi x12, x12, 2
    or   x14, x11, x12
    bne  x14, x0, debounce_wait      # Wait until both buttons are released
    jal  x0, input_wait
.end
