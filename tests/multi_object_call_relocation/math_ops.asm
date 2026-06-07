.text
.global fonksiyon_topla    # Bu fonksiyonu dışarıya açar (Linker'ın görmesi için)
.global fonksiyon_cikar    #

fonksiyon_topla:
    add  x14, x10, x11               # x14 = A + B
    jalr x0, 0(x1)                   # Ana dosyaya (main1.asm) geri dön (x1/ra üzerinden)

fonksiyon_cikar:
    sub  x14, x10, x11               # x14 = A - B
    jalr x0, 0(x1)                   # Ana dosyaya geri dön
.end