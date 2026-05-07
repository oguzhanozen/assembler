.text
dongu:
    add x1, x2, x3
    beq x1, x0, ileri
    jal x0, dongu
ileri:
    sub x1, x1, x2