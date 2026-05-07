# Negative linker demo: missing_func is extern but no object defines it.
.global main
.extern missing_func

.text
main:
    jal x1, missing_func
.end
