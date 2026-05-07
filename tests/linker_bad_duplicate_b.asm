# Negative linker demo part B: duplicate_symbol is defined globally again.
.global duplicate_symbol

.text
duplicate_symbol:
    addi x2, x0, 2
.end
