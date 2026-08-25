`default_nettype none

module smoke_dut (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       enable,
    input  logic [7:0] data_i,
    output logic [7:0] data_o,
    output logic [7:0] edge_count
);

    always_comb begin
        data_o = data_i ^ 8'hA5;
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            edge_count <= 8'h00;
        end else if (enable) begin
            edge_count <= edge_count + 8'h01;
        end
    end

endmodule

`default_nettype wire
