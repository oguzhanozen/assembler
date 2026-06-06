# Tang Nano 9K üzerindeki iki butonu okuyup LED 0 ve LED 1'de gösterir.
# BUTTON MMIO 0x10000004: bit 0 = pin 3, bit 1 = pin 4; basılı durumda 1.
.text
.global _start

_start:
    lui x5, 0x10000

loop:
    lw  x6, 4(x5)
    sw  x6, 0(x5)
    jal x0, loop
.end
