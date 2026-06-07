.data
.align 4
.global led_reg
.global s1_reg
.global s2_reg

led_reg:    .word 0x10000000
s1_reg:     .word 0x10000004
s2_reg:     .word 0x10000004

.section .bss, "aw", @nobits          # Linker-script NOBITS parsing test
.align 4
.global counter_bss
counter_bss:
    .space 4                         # Allocates 4 bytes in RAM but not in the HEX image
.end
