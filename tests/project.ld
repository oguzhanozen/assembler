ENTRY(_start);

MEMORY {
    BRAM (rwx) : ORIGIN = 0x00000000, LENGTH = 16K;
}

SECTIONS {
    .init   : ALIGN(4) { *(.init*) }   > BRAM
    .text   : ALIGN(4) { *(.text*) }   > BRAM
    .rodata : ALIGN(4) { *(.rodata*) } > BRAM
    .data   : ALIGN(4) { *(.data*) }   > BRAM
    .bss (NOLOAD) : ALIGN(4) { *(.bss*) } > BRAM
}