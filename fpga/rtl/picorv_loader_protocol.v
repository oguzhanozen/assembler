module picorv_loader_protocol #(
    parameter MEM_BYTES = 16384,
    parameter ENTRY_ADDR = 32'h00000000
) (
    input  wire        clk,
    input  wire        reset,
    input  wire [7:0]  rx_data,
    input  wire        rx_valid,
    output wire        rx_ready,
    output wire [7:0]  tx_data,
    output wire        tx_valid,
    input  wire        tx_ready,
    output reg         loader_write_valid,
    output reg [31:0]  loader_write_addr,
    output reg [7:0]   loader_write_data,
    output reg         cpu_reset
);
    localparam S_MAGIC0 = 0, S_MAGIC1 = 1, S_HEADER = 2, S_PAYLOAD = 3;
    localparam S_CRC = 4, S_EXECUTE = 5, S_WRITE = 6, S_SEND = 7, S_WAIT = 8;

    localparam T_PING = 8'h01, T_BEGIN = 8'h02, T_DATA = 8'h03;
    localparam T_END = 8'h04, T_RUN = 8'h05, T_ACK = 8'h80, T_NACK = 8'h81;

    localparam OK = 8'h00, BAD_CRC = 8'h01, BAD_SEQUENCE = 8'h02;
    localparam BAD_COMMAND = 8'h03, BAD_ADDRESS = 8'h04, BAD_LENGTH = 8'h05;
    localparam NOT_READY = 8'h06;

    reg [3:0] state = S_MAGIC0;
    reg [3:0] header_index = 0;
    reg [7:0] packet_type = 0;
    reg [7:0] packet_sequence = 0;
    reg [7:0] packet_flags = 0;
    reg [15:0] payload_length = 0;
    reg [31:0] packet_address = 0;
    reg [7:0] payload [0:127];
    reg [7:0] payload_index = 0;
    reg [1:0] crc_index = 0;
    reg [31:0] received_crc = 0;
    reg [31:0] packet_crc = 32'hFFFFFFFF;
    wire [31:0] packet_crc_next;

    reg [7:0] expected_sequence = 0;
    reg session_active = 0;
    reg image_valid = 0;
    reg [31:0] expected_bytes = 0;
    reg [31:0] received_bytes = 0;
    reg [31:0] expected_transfer_crc = 0;
    reg [31:0] transfer_crc = 32'hFFFFFFFF;
    wire [31:0] transfer_crc_next;
    reg [31:0] image_entry = ENTRY_ADDR;
    reg [7:0] write_index = 0;

    reg response_start = 0;
    reg [7:0] response_type = T_ACK;
    reg [7:0] response_status = OK;
    wire response_busy;

    wire current_byte_accepted = rx_valid && rx_ready;
    wire [7:0] crc_input = rx_data;
    wire [7:0] transfer_input = payload[write_index];

    crc32_byte packet_crc_step(
        .crc_in(packet_crc), .data_in(crc_input), .crc_out(packet_crc_next)
    );
    crc32_byte transfer_crc_step(
        .crc_in(transfer_crc), .data_in(transfer_input), .crc_out(transfer_crc_next)
    );
    uart_response_tx response_tx(
        .clk(clk), .reset(reset), .start(response_start),
        .packet_type(response_type), .sequence(packet_sequence), .status(response_status),
        .busy(response_busy), .tx_data(tx_data), .tx_valid(tx_valid), .tx_ready(tx_ready)
    );

    assign rx_ready = state == S_MAGIC0 || state == S_MAGIC1 || state == S_HEADER ||
                      state == S_PAYLOAD || state == S_CRC;

    function [31:0] payload_u32;
        input [7:0] offset;
        begin
            payload_u32 = {payload[offset+3], payload[offset+2], payload[offset+1], payload[offset]};
        end
    endfunction

    always @(posedge clk) begin
        response_start <= 1'b0;
        loader_write_valid <= 1'b0;

        if (reset) begin
            state <= S_MAGIC0;
            cpu_reset <= 1'b1;
            expected_sequence <= 0;
            session_active <= 0;
            image_valid <= 0;
            packet_crc <= 32'hFFFFFFFF;
        end else begin
            case (state)
                S_MAGIC0: if (current_byte_accepted) begin
                    if (rx_data == 8'hA5) begin
                        packet_crc <= packet_crc_next;
                        state <= S_MAGIC1;
                    end else begin
                        packet_crc <= 32'hFFFFFFFF;
                    end
                end
                S_MAGIC1: if (current_byte_accepted) begin
                    if (rx_data == 8'h5A) begin
                        packet_crc <= packet_crc_next;
                        header_index <= 0;
                        state <= S_HEADER;
                    end else begin
                        packet_crc <= rx_data == 8'hA5 ? packet_crc_next : 32'hFFFFFFFF;
                        state <= rx_data == 8'hA5 ? S_MAGIC1 : S_MAGIC0;
                    end
                end
                S_HEADER: if (current_byte_accepted) begin
                    packet_crc <= packet_crc_next;
                    case (header_index)
                        0: if (rx_data != 8'h01) begin
                            state <= S_MAGIC0;
                            packet_crc <= 32'hFFFFFFFF;
                        end
                        1: packet_type <= rx_data;
                        2: packet_sequence <= rx_data;
                        3: packet_flags <= rx_data;
                        4: payload_length[7:0] <= rx_data;
                        5: payload_length[15:8] <= rx_data;
                        6: packet_address[7:0] <= rx_data;
                        7: packet_address[15:8] <= rx_data;
                        8: packet_address[23:16] <= rx_data;
                        9: begin
                            packet_address[31:24] <= rx_data;
                            payload_index <= 0;
                            crc_index <= 0;
                            received_crc <= 0;
                            if (payload_length > 128) begin
                                response_type <= T_NACK;
                                response_status <= BAD_LENGTH;
                                state <= S_SEND;
                            end
                            else if (payload_length == 0)
                                state <= S_CRC;
                            else
                                state <= S_PAYLOAD;
                        end
                    endcase
                    if (header_index < 9)
                        header_index <= header_index + 1'b1;
                end
                S_PAYLOAD: if (current_byte_accepted) begin
                    payload[payload_index] <= rx_data;
                    packet_crc <= packet_crc_next;
                    if (payload_index + 1'b1 == payload_length) begin
                        crc_index <= 0;
                        state <= S_CRC;
                    end else begin
                        payload_index <= payload_index + 1'b1;
                    end
                end
                S_CRC: if (current_byte_accepted) begin
                    received_crc <= received_crc | ({24'b0, rx_data} << (crc_index * 8));
                    if (crc_index == 3) begin
                        if ({rx_data, received_crc[23:0]} != ~packet_crc) begin
                            response_type <= T_NACK;
                            response_status <= BAD_CRC;
                            state <= S_SEND;
                        end else if (packet_type == T_PING) begin
                            state <= S_EXECUTE;
                        end else if (packet_sequence == expected_sequence - 1'b1) begin
                            response_type <= T_ACK;
                            response_status <= OK;
                            state <= S_SEND;
                        end else if (packet_sequence != expected_sequence) begin
                            response_type <= T_NACK;
                            response_status <= BAD_SEQUENCE;
                            state <= S_SEND;
                        end else
                            state <= S_EXECUTE;
                    end else begin
                        crc_index <= crc_index + 1'b1;
                    end
                end
                S_EXECUTE: begin
                    case (packet_type)
                        T_PING: begin
                            expected_sequence <= packet_sequence + 1'b1;
                            response_type <= T_ACK;
                            response_status <= OK;
                            state <= S_SEND;
                        end
                        T_BEGIN: if (payload_length != 14 || payload_u32(0) != ENTRY_ADDR) begin
                            response_type <= T_NACK;
                            response_status <= BAD_LENGTH;
                            state <= S_SEND;
                        end else begin
                            cpu_reset <= 1'b1;
                            session_active <= 1'b1;
                            image_valid <= 1'b0;
                            image_entry <= payload_u32(0);
                            expected_bytes <= payload_u32(4);
                            expected_transfer_crc <= payload_u32(10);
                            received_bytes <= 0;
                            transfer_crc <= 32'hFFFFFFFF;
                            expected_sequence <= expected_sequence + 1'b1;
                            response_type <= T_ACK;
                            response_status <= OK;
                            state <= S_SEND;
                        end
                        T_DATA: if (!session_active) begin
                            response_type <= T_NACK;
                            response_status <= NOT_READY;
                            state <= S_SEND;
                        end else if (payload_length == 0 ||
                                     packet_address + payload_length > MEM_BYTES) begin
                            response_type <= T_NACK;
                            response_status <= BAD_ADDRESS;
                            state <= S_SEND;
                        end else begin
                            write_index <= 0;
                            state <= S_WRITE;
                        end
                        T_END: if (!session_active || payload_length != 8) begin
                            response_type <= T_NACK;
                            response_status <= NOT_READY;
                            state <= S_SEND;
                        end else if (payload_u32(0) != received_bytes ||
                                     payload_u32(0) != expected_bytes ||
                                     payload_u32(4) != ~transfer_crc ||
                                     payload_u32(4) != expected_transfer_crc) begin
                            response_type <= T_NACK;
                            response_status <= BAD_CRC;
                            state <= S_SEND;
                        end else begin
                            session_active <= 1'b0;
                            image_valid <= 1'b1;
                            expected_sequence <= expected_sequence + 1'b1;
                            response_type <= T_ACK;
                            response_status <= OK;
                            state <= S_SEND;
                        end
                        T_RUN: if (!image_valid || packet_address != image_entry) begin
                            response_type <= T_NACK;
                            response_status <= NOT_READY;
                            state <= S_SEND;
                        end else begin
                            cpu_reset <= 1'b0;
                            expected_sequence <= expected_sequence + 1'b1;
                            response_type <= T_ACK;
                            response_status <= OK;
                            state <= S_SEND;
                        end
                        default: begin
                            response_type <= T_NACK;
                            response_status <= BAD_COMMAND;
                            state <= S_SEND;
                        end
                    endcase
                end
                S_WRITE: begin
                    loader_write_valid <= 1'b1;
                    loader_write_addr <= packet_address + write_index;
                    loader_write_data <= payload[write_index];
                    transfer_crc <= transfer_crc_next;
                    received_bytes <= received_bytes + 1'b1;
                    if (write_index + 1'b1 == payload_length) begin
                        expected_sequence <= expected_sequence + 1'b1;
                        response_type <= T_ACK;
                        response_status <= OK;
                        state <= S_SEND;
                    end else begin
                        write_index <= write_index + 1'b1;
                    end
                end
                S_SEND: if (!response_busy) begin
                    response_start <= 1'b1;
                    state <= S_WAIT;
                end
                S_WAIT: if (!response_busy && !response_start) begin
                    packet_crc <= 32'hFFFFFFFF;
                    received_crc <= 0;
                    state <= S_MAGIC0;
                end
            endcase
        end
    end
endmodule
