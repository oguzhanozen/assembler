ENTRY(_start);

MEMORY {
    BRAM (rwx) : ORIGIN = 0x00000000, LENGTH = 16K;
}

SECTIONS {
    .text : ALIGN(4) { *(.text*) } > BRAM
}