module uart_response_tx (
    input  wire       clk,
    input  wire       reset,
    input  wire       start,
    input  wire [7:0] packet_type,
    input  wire [7:0] sequence,
    input  wire [7:0] status,
    output wire       busy,
    output wire [7:0] tx_data,
    output wire       tx_valid,
    input  wire       tx_ready
);
    reg active = 1'b0;
    reg [4:0] index = 0;
    reg [7:0] type_reg = 0;
    reg [7:0] sequence_reg = 0;
    reg [7:0] status_reg = 0;
    reg [31:0] crc_reg = 32'hFFFFFFFF;
    reg [31:0] final_crc = 0;
    reg [7:0] body_byte;
    wire [31:0] crc_next;

    crc32_byte crc_step(.crc_in(crc_reg), .data_in(body_byte), .crc_out(crc_next));

    always @* begin
        case (index)
            0: body_byte = 8'hA5;
            1: body_byte = 8'h5A;
            2: body_byte = 8'h01;
            3: body_byte = type_reg;
            4: body_byte = sequence_reg;
            5: body_byte = 8'h00;
            6: body_byte = 8'h01;
            7: body_byte = 8'h00;
            8, 9, 10, 11: body_byte = 8'h00;
            12: body_byte = status_reg;
            13: body_byte = final_crc[7:0];
            14: body_byte = final_crc[15:8];
            15: body_byte = final_crc[23:16];
            default: body_byte = final_crc[31:24];
        endcase
    end

    assign busy = active;
    assign tx_valid = active;
    assign tx_data = body_byte;

    always @(posedge clk) begin
        if (reset) begin
            active <= 1'b0;
            index <= 0;
            crc_reg <= 32'hFFFFFFFF;
        end else begin
            if (start && !active) begin
                active <= 1'b1;
                index <= 0;
                type_reg <= packet_type;
                sequence_reg <= sequence;
                status_reg <= status;
                crc_reg <= 32'hFFFFFFFF;
            end else if (active && tx_ready) begin
                if (index < 13) begin
                    crc_reg <= crc_next;
                    if (index == 12)
                        final_crc <= ~crc_next;
                end
                if (index == 16) begin
                    active <= 1'b0;
                    index <= 0;
                end else begin
                    index <= index + 1'b1;
                end
            end
        end
    end
endmodule
