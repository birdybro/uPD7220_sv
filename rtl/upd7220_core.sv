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
    logic       command_start;
    logic       unused_command_known;
    upd7220_pkg::command_kind_t started_kind;
    logic [7:0] started_opcode;
    logic [4:0] unused_started_parameter_limit;
    logic       parameter_valid;
    logic [7:0] parameter_data;
    logic [3:0] parameter_index;
    upd7220_pkg::command_kind_t parameter_kind;
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
    logic       sync_display_enable;
    logic       sync_master;
    logic [7:0] unused_sync_programmed_mask;
    logic [7:0] unused_sync_p1;
    logic [7:0] unused_sync_p2;
    logic [7:0] unused_sync_p3;
    logic [7:0] unused_sync_p4;
    logic [7:0] unused_sync_p5;
    logic [7:0] unused_sync_p6;
    logic [7:0] unused_sync_p7;
    logic [7:0] unused_sync_p8;
    upd7220_pkg::display_mode_t unused_display_mode;
    upd7220_pkg::framing_mode_t unused_framing_mode;
    logic       unused_refresh_enable;
    logic       unused_drawing_during_retrace_only;
    logic [8:0] sync_active_words;
    logic [8:0] unused_base_pitch;
    logic [5:0] sync_hsync_width;
    logic [5:0] sync_vsync_width;
    logic [6:0] sync_horizontal_front_porch;
    logic [6:0] sync_horizontal_back_porch;
    logic [6:0] sync_vertical_front_porch;
    logic [10:0] sync_active_lines;
    logic [6:0] sync_vertical_back_porch;
    logic       unused_horizontal_blank;
    logic       unused_active_word;
    logic       unused_line_start;
    upd7220_pkg::horizontal_phase_t unused_horizontal_phase;
    logic [8:0] unused_horizontal_word_index;
    logic       timing_line_advance;
    logic       timing_vertical_blank;
    logic       unused_active_line;
    logic       unused_field_start;
    upd7220_pkg::vertical_phase_t unused_vertical_phase;
    logic [10:0] unused_vertical_line_index;

    assign _unused_inputs = ^{
        v_ext_sync_i,
        dack_n,
        mem_ad_i,
        lpen,
        unused_fifo_read_direction,
        unused_fifo_occupancy,
        unused_response_ready,
        unused_command_known,
        unused_started_parameter_limit,
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
        unused_sync_programmed_mask,
        unused_sync_p1,
        unused_sync_p2,
        unused_sync_p3,
        unused_sync_p4,
        unused_sync_p5,
        unused_sync_p6,
        unused_sync_p7,
        unused_sync_p8,
        unused_display_mode,
        unused_framing_mode,
        unused_refresh_enable,
        unused_drawing_during_retrace_only,
        unused_base_pitch,
        unused_horizontal_blank,
        unused_active_word,
        unused_line_start,
        unused_horizontal_phase,
        unused_horizontal_word_index,
        unused_active_line,
        unused_field_start,
        unused_vertical_phase,
        unused_vertical_line_index,
        idle_q
    };

    assign status_value = device_initialized_q
        ? {5'b0, fifo_empty, fifo_full, fifo_data_ready}
        : 8'hxx;
    assign v_ext_sync_oe = sync_master;

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
        .command_start,
        .command_known             (unused_command_known),
        .started_kind,
        .started_opcode,
        .started_parameter_limit   (unused_started_parameter_limit),
        .parameter_valid,
        .parameter_data,
        .parameter_index,
        .parameter_kind,
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

    upd7220_sync_control #(
        .GDC_VARIANT
    ) sync_control (
        .clk_2x,
        .integration_reset_n,
        .reset_command,
        .command_start,
        .started_kind,
        .started_opcode,
        .parameter_valid,
        .parameter_kind,
        .parameter_index,
        .parameter_data,
        .display_enable            (sync_display_enable),
        .sync_master,
        .programmed_mask           (unused_sync_programmed_mask),
        .sync_p1                   (unused_sync_p1),
        .sync_p2                   (unused_sync_p2),
        .sync_p3                   (unused_sync_p3),
        .sync_p4                   (unused_sync_p4),
        .sync_p5                   (unused_sync_p5),
        .sync_p6                   (unused_sync_p6),
        .sync_p7                   (unused_sync_p7),
        .sync_p8                   (unused_sync_p8),
        .display_mode              (unused_display_mode),
        .framing_mode              (unused_framing_mode),
        .refresh_enable            (unused_refresh_enable),
        .drawing_during_retrace_only (unused_drawing_during_retrace_only),
        .active_words              (sync_active_words),
        .base_pitch                (unused_base_pitch),
        .hsync_width               (sync_hsync_width),
        .vsync_width               (sync_vsync_width),
        .horizontal_front_porch    (sync_horizontal_front_porch),
        .horizontal_back_porch     (sync_horizontal_back_porch),
        .vertical_front_porch      (sync_vertical_front_porch),
        .active_lines              (sync_active_lines),
        .vertical_back_porch       (sync_vertical_back_porch)
    );

    upd7220_video_timing video_timing (
        .clk_2x,
        .integration_reset_n,
        .reset_command,
        .word_time_ce,
        .display_enable             (sync_display_enable),
        .active_words               (sync_active_words),
        .hsync_width                (sync_hsync_width),
        .horizontal_front_porch     (sync_horizontal_front_porch),
        .horizontal_back_porch      (sync_horizontal_back_porch),
        .vertical_blank             (timing_vertical_blank),
        .hsync,
        .horizontal_blank           (unused_horizontal_blank),
        .blank,
        .active_word                (unused_active_word),
        .line_start                 (unused_line_start),
        .line_advance_ce            (timing_line_advance),
        .horizontal_phase           (unused_horizontal_phase),
        .horizontal_word_index      (unused_horizontal_word_index)
    );

    upd7220_vertical_timing vertical_timing (
        .clk_2x,
        .integration_reset_n,
        .reset_command,
        .line_advance_ce             (timing_line_advance),
        .vsync_width                 (sync_vsync_width),
        .vertical_front_porch       (sync_vertical_front_porch),
        .active_lines               (sync_active_lines),
        .vertical_back_porch        (sync_vertical_back_porch),
        .vsync                      (v_ext_sync_o),
        .vertical_blank             (timing_vertical_blank),
        .active_line                (unused_active_line),
        .field_start                (unused_field_start),
        .vertical_phase             (unused_vertical_phase),
        .vertical_line_index        (unused_vertical_line_index)
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
