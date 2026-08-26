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
    logic device_initialized_q;
    logic idle_q;
    logic [7:0] status_value;
    logic       fifo_write_valid;
    logic       fifo_write_is_command;
    logic [7:0] fifo_write_data;
    logic       fifo_read_pop;
    logic       reset_command;
    logic [7:0] fifo_read_data;
    logic       fifo_empty;
    logic       fifo_full;
    logic       fifo_data_ready;
    logic       command_valid;
    logic       command_is_command;
    logic [7:0] command_data;
    logic       command_pop;
    logic       unused_fifo_read_direction;
    logic [4:0] unused_fifo_occupancy;
    logic       unused_response_ready;
    logic       unused_command_start;
    logic       unused_command_known;
    upd7220_pkg::command_kind_t unused_started_kind;
    logic [7:0] unused_started_opcode;
    logic [4:0] unused_started_parameter_limit;
    logic       unused_parameter_valid;
    logic [7:0] unused_parameter_data;
    logic [3:0] unused_parameter_index;
    upd7220_pkg::command_kind_t unused_parameter_kind;
    logic [7:0] unused_parameter_opcode;
    logic       unused_command_complete;
    logic [7:0] unused_completed_opcode;
    logic       unused_command_interrupted;
    logic [7:0] unused_interrupted_opcode;
    logic       unused_unexpected_parameter;
    logic       unused_command_active;
    upd7220_pkg::command_kind_t unused_active_kind;
    logic [7:0] unused_active_opcode;
    logic [3:0] unused_next_parameter_index;

    assign _unused_inputs = ^{
        v_ext_sync_i,
        dack_n,
        mem_ad_i,
        lpen,
        unused_fifo_read_direction,
        unused_fifo_occupancy,
        unused_response_ready,
        unused_command_start,
        unused_command_known,
        unused_started_kind,
        unused_started_opcode,
        unused_started_parameter_limit,
        unused_parameter_valid,
        unused_parameter_data,
        unused_parameter_index,
        unused_parameter_kind,
        unused_parameter_opcode,
        unused_command_complete,
        unused_completed_opcode,
        unused_command_interrupted,
        unused_interrupted_opcode,
        unused_unexpected_parameter,
        unused_command_active,
        unused_active_kind,
        unused_active_opcode,
        unused_next_parameter_index,
        idle_q
    };

    assign status_value = device_initialized_q
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
        .fifo_read_pop,
        .reset_command
    );

    upd7220_fifo fifo (
        .clk_2x,
        .integration_reset_n,
        .fifo_reset                (reset_command),
        .host_write_valid          (fifo_write_valid),
        .host_write_is_command     (fifo_write_is_command),
        .host_write_data           (fifo_write_data),
        .host_read_pop             (fifo_read_pop),
        .command_valid,
        .command_is_command,
        .command_data,
        .command_pop,
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

    upd7220_command command_processor (
        .clk_2x,
        .integration_reset_n,
        .reset_command,
        .processor_enable          (1'b1),
        .fifo_valid                (command_valid),
        .fifo_is_command           (command_is_command),
        .fifo_data                 (command_data),
        .fifo_pop                  (command_pop),
        .command_start             (unused_command_start),
        .command_known             (unused_command_known),
        .started_kind              (unused_started_kind),
        .started_opcode            (unused_started_opcode),
        .started_parameter_limit   (unused_started_parameter_limit),
        .parameter_valid           (unused_parameter_valid),
        .parameter_data            (unused_parameter_data),
        .parameter_index           (unused_parameter_index),
        .parameter_kind            (unused_parameter_kind),
        .parameter_opcode          (unused_parameter_opcode),
        .command_complete          (unused_command_complete),
        .completed_opcode          (unused_completed_opcode),
        .command_interrupted       (unused_command_interrupted),
        .interrupted_opcode        (unused_interrupted_opcode),
        .unexpected_parameter      (unused_unexpected_parameter),
        .command_active            (unused_command_active),
        .active_kind               (unused_active_kind),
        .active_opcode             (unused_active_opcode),
        .next_parameter_index      (unused_next_parameter_index)
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
            device_initialized_q <= 1'b0;
            idle_q       <= 1'b1;
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
        end else if (reset_command) begin
            device_initialized_q <= 1'b1;
            idle_q               <= 1'b1;
            word_half_q          <= 1'b0;
            word_time_ce         <= 1'b0;
            mem_dbin_n           <= 1'b1;
            hsync                <= 1'b0;
            v_ext_sync_o         <= 1'b0;
            v_ext_sync_oe        <= 1'b0;
            blank                <= 1'b1;
            mem_ale              <= 1'b1;
            drq                  <= 1'b0;
            mem_ad_o             <= 16'h0000;
            mem_ad_oe            <= 1'b0;
            mem_a16              <= 1'b0;
            mem_a17              <= 1'b0;
        end else begin
            word_half_q  <= ~word_half_q;
            word_time_ce <= word_half_q;
        end
    end

endmodule

`default_nettype wire
