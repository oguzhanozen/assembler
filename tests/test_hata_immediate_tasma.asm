# Test: Immediate degeri tasma hatasi (basarisiz)
.text
main:
    # 12-bit immediate ust siniri 2047'dir. Bu deger hataya dusmeli.
    addi x1, x0, 4096
.end
