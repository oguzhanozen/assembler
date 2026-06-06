.data
.align 4
.global led_ptr
.global s1_ptr
.global s2_ptr
.global test_pattern

led_ptr:       .word 0x10000000
s1_ptr:        .word 0x10000004
s2_ptr:        .word 0x10000004
test_pattern:  .word 0x000000AA      # Sınır testlerinde belleğe yazılacak veri maskesi
.end
