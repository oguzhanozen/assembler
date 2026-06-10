.text
.global fonksiyon_topla    # Export add function to the linker
.global fonksiyon_cikar    # Export subtract function to the linker

fonksiyon_topla:
    add  x14, x10, x11               # x14 = A + B
    jalr x0, 0(x1)                   # Return to main1.asm through x1/ra

fonksiyon_cikar:
    sub  x14, x10, x11               # x14 = A - B
    jalr x0, 0(x1)                   # Return to the caller
.end
