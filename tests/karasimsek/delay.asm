.text

.global delay_start

.extern loop

delay_start:
    addi x7, x7, -1
    bne  x7, x0, delay_start

    slli x6, x6, 1          # LED desenini sola kaydır
    addi x8, x0, 64         # Altı LED tamamlandıktan sonra başa dön
    bne  x6, x8, loop       # loop başka dosyada

    addi x6, x0, 1
    jal  x0, loop           # loop başka dosyada
