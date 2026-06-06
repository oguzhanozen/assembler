ENTRY(_start);

MEMORY {
    ROM (rx) : ORIGIN = 0x00000000, LENGTH = 16K;
    RAM (rw) : ORIGIN = 0x00010000, LENGTH = 4K;
}

SECTIONS {
    .init   : ALIGN(4) { *(.init*) }   > ROM
    .text   : ALIGN(4) { *(.text*) }   > ROM
    .rodata : ALIGN(4) { *(.rodata*) } > ROM
    .data   : ALIGN(4) { *(.data*) }   > RAM
    .bss (NOLOAD) : ALIGN(4) { *(.bss*) } > RAM
}
