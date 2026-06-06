.init
.text
.global _start
.extern fonksiyon_topla    # Linker'a bu fonksiyonun harici dosyada olduğunu bildirir
.extern fonksiyon_cikar    # Linker bu sembollerin adresini link aşamasında bağlayacak

_start:
    # Adresleri .data segmentinden dinamik çöz (Relocation Kontrolü)
    lui  x5, %hi(led_addr)
    lw   x6, %lo(led_addr)(x5)       # x6 = 0x10000000 (LED)
    lui  x5, %hi(s1_addr)
    lw   x7, %lo(s1_addr)(x5)        # x7 = 0x10000004 (buton durum register'i)
    lui  x5, %hi(s2_addr)
    lw   x8, %lo(s2_addr)(x5)        # x8 = 0x10000004 (aynı register)

    # İşlem görecek sabit girdi parametreleri
    addi x10, x0, 12                 # A = 12
    addi x11, x0, 4                  # B = 4

main_loop:
    lw   x12, 0(x7)                  # S1 butonunu oku
    andi x12, x12, 1
    bne  x12, x0, call_topla         # S1 (bit 0) basıldıysa harici toplayıcıyı çağır

    lw   x13, 0(x8)                  # S2 butonunu oku
    andi x13, x13, 2
    bne  x13, x0, call_cikar         # S2 (bit 1) basıldıysa harici çıkarıcıyı çağır

    # Basılmadıysa LED'leri kapat
    addi x14, x0, 0
    sw   x14, 0(x6)
    jal  x0, main_loop

call_topla:
    jal  x1, fonksiyon_topla         # Diğer dosyadaki fonksiyona dallan (ra = x1)
    jal  x0, ekrana_bas

call_cikar:
    jal  x1, fonksiyon_cikar         # Diğer dosyadaki fonksiyona dallan (ra = x1)

ekrana_bas:
    sw   x14, 0(x6)                  # Sonucu doğrudan LED bit deseni olarak yaz
    jal  x0, main_loop

.data
.align 4
led_addr:   .word 0x10000000
s1_addr:    .word 0x10000004
s2_addr:    .word 0x10000004
.end
