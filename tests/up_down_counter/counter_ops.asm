.text
.global increment_count
.global decrement_count
.extern save_and_show

increment_count:
    addi x9, x9, 1
    addi x10, x0, 64
    blt  x9, x10, jump_to_show
    addi x9, x0, 0

jump_to_show:
    jal  x0, save_and_show

decrement_count:
    addi x9, x9, -1
    bge  x9, x0, jump_to_show
    addi x9, x0, 63
    jal  x0, save_and_show