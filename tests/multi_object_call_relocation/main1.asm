.init
.text
.global _start
.extern fonksiyon_topla    # Function is defined in another object
.extern fonksiyon_cikar    # Linker resolves this external function

_start:
    # Resolve addresses from .data by applying relocation records
    lui  x5, %hi(led_addr)
    lw   x6, %lo(led_addr)(x5)       # x6 = 0x10000000, LED address
    lui  x5, %hi(s1_addr)
    lw   x7, %lo(s1_addr)(x5)        # x7 = 0x10000004, button status register
    lui  x5, %hi(s2_addr)
    lw   x8, %lo(s2_addr)(x5)        # x8 = 0x10000004, same status register

    # Constant input operands
    addi x10, x0, 12                 # A = 12
    addi x11, x0, 4                  # B = 4

main_loop:
    lw   x12, 0(x7)                  # Read S1
    andi x12, x12, 1
    bne  x12, x0, call_topla         # Call external add function when S1 is pressed

    lw   x13, 0(x8)                  # Read S2
    andi x13, x13, 2
    bne  x13, x0, call_cikar         # Call external subtract function when S2 is pressed

    # Turn LEDs off when no button is pressed
    addi x14, x0, 0
    sw   x14, 0(x6)
    jal  x0, main_loop

call_topla:
    jal  x1, fonksiyon_topla         # Call function from another object (ra = x1)
    jal  x0, ekrana_bas

call_cikar:
    jal  x1, fonksiyon_cikar         # Call function from another object (ra = x1)

ekrana_bas:
    sw   x14, 0(x6)                  # Display result as an LED bit pattern
    jal  x0, main_loop

.data
.align 4
led_addr:   .word 0x10000000
s1_addr:    .word 0x10000004
s2_addr:    .word 0x10000004
.end
