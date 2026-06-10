.text
.global fonksiyon_topla
.global fonksiyon_cikar

fonksiyon_topla:
    add  x14, x10, x11
    jalr x0, 0(x1)

fonksiyon_cikar:
    sub  x14, x10, x11
    jalr x0, 0(x1)