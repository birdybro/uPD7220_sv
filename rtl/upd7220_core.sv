`default_nettype none

module upd7220_core #(
    parameter upd7220_pkg::gdc_variant_t GDC_VARIANT = upd7220_pkg::GDC_7220
) (
    input  logic        clk_2x,
    input  logic        integration_reset_n,

    input  logic        host_rd_n,
    input  logic        host_wr_n,
    input  logic        host_a0,
    input  logic [upd7220_pkg::HOST_DATA_WIDTH-1:0] host_db_i,
    output logic [upd7220_pkg::HOST_DATA_WIDTH-1:0] host_db_o,
    output logic        host_db_oe,

    output logic        mem_dbin_n,
    output logic        hsync,
    input  logic        v_ext_sync_i,
    output logic        v_ext_sync_o,
    output logic        v_ext_sync_oe,
    output logic        blank,
    output logic        mem_ale,
    output logic        drq,
    input  logic        dack_n,
    input  logic [upd7220_pkg::MEM_DATA_WIDTH-1:0] mem_ad_i,
    output logic [upd7220_pkg::MEM_DATA_WIDTH-1:0] mem_ad_o,
    output logic        mem_ad_oe,
    output logic        mem_a16,
    output logic        mem_a17,
    input  logic        lpen,

    output logic        word_time_ce
);

    logic word_half_q;
    logic _unused_inputs;

    assign _unused_inputs = ^{
        host_rd_n,
        host_wr_n,
        host_a0,
        host_db_i,
        v_ext_sync_i,
        dack_n,
        mem_ad_i,
        lpen
    };

    generate
        if (!upd7220_pkg::valid_variant(GDC_VARIANT)) begin : g_invalid_variant
            initial $error("GDC_VARIANT is not a supported uPD7220 family profile");
        end
    endgenerate

    // This reset is an FPGA/integration facility, not a pin on the original IC.
    // All functional timing remains clocked from 2xWCLK; no derived clock exists.
    always_ff @(posedge clk_2x or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            word_half_q  <= 1'b0;
            word_time_ce <= 1'b0;
            host_db_o    <= 8'h00;
            host_db_oe   <= 1'b0;
            mem_dbin_n   <= 1'b1;
            hsync        <= 1'b0;
            v_ext_sync_o <= 1'b0;
            v_ext_sync_oe <= 1'b0;
            blank        <= 1'b1;
            mem_ale      <= 1'b1;
            drq          <= 1'b0;
            mem_ad_o     <= 16'h0000;
            mem_ad_oe    <= 1'b0;
            mem_a16      <= 1'b0;
            mem_a17      <= 1'b0;
        end else begin
            word_half_q  <= ~word_half_q;
            word_time_ce <= word_half_q;
        end
    end

endmodule

`default_nettype wire
