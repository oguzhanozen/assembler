ENTRY(_start);

MEMORY {
    BRAM (rwx) : ORIGIN = 0x00000000, LENGTH = 16K;
}

SECTIONS {
    .text : ALIGN(4) {
        main.o(.text)
        delay.o(.text)
        *(.text*)
    } > BRAM

    .rodata : ALIGN(4) {
        *(.rodata*)
    } > BRAM

    .data : ALIGN(4) {
        *(.data*)
    } > BRAM

    .bss (NOLOAD) : ALIGN(4) {
        *(.bss*)
    } > BRAM
}
