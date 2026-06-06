module tang_nano_9k_top (
    input  wire       clk_27mhz,
    input  wire       reset_button_n,
    input  wire       uart_rx_pin,
    output wire       uart_tx_pin,
    output wire [5:0] led_n
);
    localparam UART_PRESCALE = 16'd29; // 27 MHz / (115200 * 8), rounded

    wire reset = !reset_button_n;
    wire [7:0] rx_data;
    wire rx_valid;
    wire rx_ready;
    wire [7:0] tx_data;
    wire tx_valid;
    wire tx_ready;
    wire loader_write_valid;
    wire [31:0] loader_write_addr;
    wire [7:0] loader_write_data;
    wire cpu_reset;
    wire [5:0] led;
    wire trap;

    uart_rx uart_rx_inst (
        .clk(clk_27mhz), .rst(reset), .m_axis_tdata(rx_data),
        .m_axis_tvalid(rx_valid), .m_axis_tready(rx_ready), .rxd(uart_rx_pin),
        .busy(), .overrun_error(), .frame_error(), .prescale(UART_PRESCALE)
    );
    uart_tx uart_tx_inst (
        .clk(clk_27mhz), .rst(reset), .s_axis_tdata(tx_data),
        .s_axis_tvalid(tx_valid), .s_axis_tready(tx_ready), .txd(uart_tx_pin),
        .busy(), .prescale(UART_PRESCALE)
    );
    picorv_loader_protocol loader (
        .clk(clk_27mhz), .reset(reset), .rx_data(rx_data), .rx_valid(rx_valid),
        .rx_ready(rx_ready), .tx_data(tx_data), .tx_valid(tx_valid), .tx_ready(tx_ready),
        .loader_write_valid(loader_write_valid), .loader_write_addr(loader_write_addr),
        .loader_write_data(loader_write_data), .cpu_reset(cpu_reset)
    );
    picorv_system system (
        .clk(clk_27mhz), .reset(reset), .loader_write_valid(loader_write_valid),
        .loader_write_addr(loader_write_addr), .loader_write_data(loader_write_data),
        .cpu_reset(cpu_reset), .led(led), .trap(trap)
    );

    assign led_n = ~(led | {5'b0, trap});
endmodule
