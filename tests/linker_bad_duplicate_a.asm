# Negative linker demo part A: duplicate_symbol is defined globally here.
.global duplicate_symbol

.text
duplicate_symbol:
    addi x1, x0, 1
.end
