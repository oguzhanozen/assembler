.data
.align 4
.global led_reg
.global s1_reg
.global s2_reg

led_reg:    .word 0x10000000
s1_reg:     .word 0x10000004
s2_reg:     .word 0x10000004

.section .bss, "aw", @nobits          # Linker Script'in NOBITS ayrıştırma testi
.align 4
.global counter_bss
counter_bss:
    .space 4                         # RAM'de 4 byte yer ayırır ama hex dosyasında yer kaplamaz
.end
