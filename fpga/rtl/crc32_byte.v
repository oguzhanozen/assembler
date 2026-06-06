module crc32_byte (
    input  wire [31:0] crc_in,
    input  wire [7:0]  data_in,
    output wire [31:0] crc_out
);
    integer i;
    reg [31:0] crc;

    always @* begin
        crc = crc_in ^ data_in;
        for (i = 0; i < 8; i = i + 1)
            crc = crc[0] ? ((crc >> 1) ^ 32'hEDB88320) : (crc >> 1);
    end

    assign crc_out = crc;
endmodule
