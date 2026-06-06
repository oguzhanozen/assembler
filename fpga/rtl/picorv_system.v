module picorv_system #(
    parameter MEM_WORDS = 4096,
    parameter LED_ADDR = 32'h10000000
) (
    input  wire       clk,
    input  wire       reset,
    input  wire       loader_write_valid,
    input  wire [31:0] loader_write_addr,
    input  wire [7:0] loader_write_data,
    input  wire       cpu_reset,
    output reg  [5:0] led,
    output wire       trap
);
    reg [7:0] memory0 [0:MEM_WORDS-1];
    reg [7:0] memory1 [0:MEM_WORDS-1];
    reg [7:0] memory2 [0:MEM_WORDS-1];
    reg [7:0] memory3 [0:MEM_WORDS-1];

    wire mem_valid;
    wire mem_instr;
    reg mem_ready = 0;
    wire [31:0] mem_addr;
    wire [31:0] mem_wdata;
    wire [3:0] mem_wstrb;
    reg [31:0] mem_rdata = 0;

    wire ram_access = mem_addr < MEM_WORDS * 4;
    wire loader_ram_write = cpu_reset && loader_write_valid && loader_write_addr < MEM_WORDS * 4;
    wire cpu_ram_write = !cpu_reset && mem_valid && ram_access && |mem_wstrb;
    wire [11:0] ram_addr = cpu_reset ? loader_write_addr[13:2] : mem_addr[13:2];
    wire [3:0] ram_wstrb = loader_ram_write
        ? (4'b0001 << loader_write_addr[1:0])
        : (cpu_ram_write ? mem_wstrb : 4'b0000);
    wire [31:0] ram_wdata = loader_ram_write
        ? ({24'b0, loader_write_data} << (loader_write_addr[1:0] * 8))
        : mem_wdata;
    wire [31:0] ram_rdata = {memory3[ram_addr], memory2[ram_addr], memory1[ram_addr], memory0[ram_addr]};

    picorv32 #(
        .PROGADDR_RESET(32'h00000000),
        .STACKADDR(MEM_WORDS * 4),
        .ENABLE_COUNTERS(0),
        .ENABLE_COUNTERS64(0),
        .ENABLE_PCPI(0),
        .ENABLE_IRQ(0)
    ) cpu (
        .clk(clk),
        .resetn(!reset && !cpu_reset),
        .trap(trap),
        .mem_valid(mem_valid),
        .mem_instr(mem_instr),
        .mem_ready(mem_ready),
        .mem_addr(mem_addr),
        .mem_wdata(mem_wdata),
        .mem_wstrb(mem_wstrb),
        .mem_rdata(mem_rdata),
        .pcpi_wr(1'b0),
        .pcpi_rd(32'b0),
        .pcpi_wait(1'b0),
        .pcpi_ready(1'b0),
        .irq(32'b0)
    );

    always @(posedge clk) begin
        if (ram_wstrb[0])
            memory0[ram_addr] <= ram_wdata[7:0];
        if (ram_wstrb[1])
            memory1[ram_addr] <= ram_wdata[15:8];
        if (ram_wstrb[2])
            memory2[ram_addr] <= ram_wdata[23:16];
        if (ram_wstrb[3])
            memory3[ram_addr] <= ram_wdata[31:24];

        mem_ready <= 1'b0;
        if (reset) begin
            led <= 0;
            mem_rdata <= 0;
        end else if (!cpu_reset && mem_valid && !mem_ready) begin
            mem_ready <= 1'b1;
            if (mem_addr == LED_ADDR) begin
                if (|mem_wstrb)
                    led <= mem_wdata[5:0];
                mem_rdata <= {26'b0, led};
            end else if (ram_access) begin
                mem_rdata <= ram_rdata;
            end else begin
                mem_rdata <= 0;
            end
        end
    end
endmodule
