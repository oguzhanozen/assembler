set_device -name GW1NR-9C GW1NR-LV9QN88PC6/I5

add_file rtl/vendor/picorv32.v
add_file rtl/vendor/uart_rx.v
add_file rtl/vendor/uart_tx.v
add_file rtl/crc32_byte.v
add_file rtl/uart_response_tx.v
add_file rtl/picorv_loader_protocol.v
add_file rtl/picorv_system.v
add_file rtl/tang_nano_9k_top.v
add_file tang_nano_9k.cst
add_file tang_nano_9k.sdc

set_option -top_module tang_nano_9k_top
set_option -output_base_name picorv_loader
run all

file mkdir ../outputs/fpga
file copy -force impl/pnr/picorv_loader.fs ../outputs/fpga/picorv_loader.fs
