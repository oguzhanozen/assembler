.init
.text
.global _start
.extern led_ptr            # External symbols resolved by the linker
.extern s1_ptr
.extern s2_ptr
.extern test_pattern       # Test pattern defined in another object

_start:
    lui  x5, %hi(led_ptr)
    lw   x6, %lo(led_ptr)(x5)        # x6 = LED address
    lui  x5, %hi(s1_ptr)
    lw   x7, %lo(s1_ptr)(x5)         # x7 = S1 address
    lui  x5, %hi(s2_ptr)
    lw   x8, %lo(s2_ptr)(x5)         # x8 = S2 address

    # Load external test data by applying a relocation record
    lui  x5, %hi(test_pattern)
    lw   x10, %lo(test_pattern)(x5)  # x10 = 0x000000AA

main_check:
    lw   x11, 0(x7)                  # Read S1
    andi x11, x11, 1
    bne  x11, x0, safe_boundary_write # Write to the valid boundary when S1 is pressed

    lw   x12, 0(x8)                  # Read S2
    andi x12, x12, 2
    bne  x12, x0, overflow_forced_write # Trigger out-of-range write when S2 is pressed

    jal  x0, main_check

safe_boundary_write:
    # Last valid word address of the 16 KiB BRAM: 0x00003FFC
    lui  x13, 4                      # x13 = 0x00004000
    addi x13, x13, -4                # x13 = 0x00003FFC, last valid address

    sw   x10, 0(x13)                 # Write inside the valid boundary

    addi x14, x0, 1                  # Success code: 0x01
    sw   x14, 0(x6)                  # Turn on LED0 to indicate success
    jal  x0, debounce_loop

overflow_forced_write:
    # First address outside the 16 KiB BRAM: 0x00004000
    lui  x13, 1
    slli x13, x13, 4                 # x13 = 0x00004000, boundary violation

    sw   x10, 0(x13)                 # Force an out-of-range hardware write

    addi x14, x0, 0x3F               # Error code: 0x3F, all LEDs
    sw   x14, 0(x6)                  # Turn on all LEDs to indicate an error

debounce_loop:
    lw   x11, 0(x7)
    andi x11, x11, 1
    lw   x12, 0(x8)
    andi x12, x12, 2
    or   x14, x11, x12
    bne  x14, x0, debounce_loop      # Wait until both buttons are released
    jal  x0, main_check
.end
