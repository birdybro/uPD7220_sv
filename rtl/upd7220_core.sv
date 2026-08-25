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
    logic integration_initialized_q;
    logic [7:0] status_value;
    logic       fifo_write_valid;
    logic       fifo_write_is_command;
    logic [7:0] fifo_write_data;
    logic       fifo_read_pop;
    logic [7:0] fifo_read_data;
    logic       fifo_empty;
    logic       fifo_full;
    logic       fifo_data_ready;
    logic       unused_command_valid;
    logic       unused_command_is_command;
    logic [7:0] unused_command_data;
    logic       unused_fifo_read_direction;
    logic [4:0] unused_fifo_occupancy;
    logic       unused_response_ready;

    assign _unused_inputs = ^{
        v_ext_sync_i,
        dack_n,
        mem_ad_i,
        lpen,
        unused_command_valid,
        unused_command_is_command,
        unused_command_data,
        unused_fifo_read_direction,
        unused_fifo_occupancy,
        unused_response_ready
    };

    assign status_value = integration_initialized_q
        ? {5'b0, fifo_empty, fifo_full, fifo_data_ready}
        : 8'hxx;

    upd7220_host_if host_if (
        .clk_2x,
        .integration_reset_n,
        .host_rd_n,
        .host_wr_n,
        .host_a0,
        .host_db_i,
        .host_db_o,
        .host_db_oe,
        .status_i                  (status_value),
        .fifo_read_data_i          (fifo_read_data),
        .fifo_write_valid,
        .fifo_write_is_command,
        .fifo_write_data,
        .fifo_read_pop
    );

    upd7220_fifo fifo (
        .clk_2x,
        .integration_reset_n,
        .fifo_reset                (1'b0),
        .host_write_valid          (fifo_write_valid),
        .host_write_is_command     (fifo_write_is_command),
        .host_write_data           (fifo_write_data),
        .host_read_pop             (fifo_read_pop),
        .command_valid             (unused_command_valid),
        .command_is_command        (unused_command_is_command),
        .command_data              (unused_command_data),
        .command_pop               (1'b0),
        .turn_to_read              (1'b0),
        .response_valid            (1'b0),
        .response_data             (8'h00),
        .response_ready            (unused_response_ready),
        .host_read_data            (fifo_read_data),
        .fifo_empty,
        .fifo_full,
        .data_ready                (fifo_data_ready),
        .read_direction            (unused_fifo_read_direction),
        .occupancy                 (unused_fifo_occupancy)
    );

    generate
        if (!upd7220_pkg::valid_variant(GDC_VARIANT)) begin : g_invalid_variant
            initial $error("GDC_VARIANT is not a supported uPD7220 family profile");
        end
    endgenerate

    // This reset is an FPGA/integration facility, not a pin on the original IC.
    // All functional timing remains clocked from 2xWCLK; no derived clock exists.
    always_ff @(posedge clk_2x or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            integration_initialized_q <= 1'b1;
            word_half_q  <= 1'b0;
            word_time_ce <= 1'b0;
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
