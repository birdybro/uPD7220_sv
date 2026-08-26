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
    logic       fifo_response_ready;
    logic       cursor_turn_to_read;
    logic       cursor_response_valid;
    logic [7:0] cursor_response_data;
    logic       command_start;
    logic       unused_command_known;
    upd7220_pkg::command_kind_t started_kind;
    logic [7:0] started_opcode;
    logic [4:0] unused_started_parameter_limit;
    logic       parameter_valid;
    logic [7:0] parameter_data;
    logic [3:0] parameter_index;
    upd7220_pkg::command_kind_t parameter_kind;
    logic [7:0] parameter_opcode;
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
    upd7220_pkg::display_mode_t sync_display_mode;
    upd7220_pkg::framing_mode_t unused_framing_mode;
    logic       unused_refresh_enable;
    logic       unused_drawing_during_retrace_only;
    logic [8:0] sync_active_words;
    logic [5:0] sync_hsync_width;
    logic [5:0] sync_vsync_width;
    logic [6:0] sync_horizontal_front_porch;
    logic [6:0] sync_horizontal_back_porch;
    logic [6:0] sync_vertical_front_porch;
    logic [10:0] sync_active_lines;
    logic [6:0] sync_vertical_back_porch;
    logic       unused_horizontal_blank;
    logic       timing_active_word;
    logic       timing_line_start;
    upd7220_pkg::horizontal_phase_t unused_horizontal_phase;
    logic [8:0] unused_horizontal_word_index;
    logic       timing_line_advance;
    logic       timing_vertical_blank;
    logic       timing_active_line;
    logic       unused_field_start;
    upd7220_pkg::vertical_phase_t unused_vertical_phase;
    logic [10:0] unused_vertical_line_index;
    logic [8:0] display_pitch;
    logic [17:0] unused_ead;
    logic [3:0] unused_dot_address;
    logic [15:0] unused_mask;
    logic [127:0] display_parameter_ram;
    logic [15:0] unused_pram_programmed_mask;
    logic       raster_partition_active;
    logic [1:0] unused_partition_index;
    logic [10:0] unused_partition_line_index;
    logic [10:0] unused_partition_line_count;
    logic [5:0] unused_character_scanline;
    logic [17:0] unused_partition_start_address;
    logic [17:0] raster_dad;
    logic       unused_image_area;
    logic       unused_graphics_area;
    logic       unused_wide_access;
    logic       mem_request_ready;
    logic       mem_response_valid;
    upd7220_pkg::memory_cycle_kind_t unused_mem_response_kind;
    logic [17:0] mem_response_address;
    logic [15:0] mem_response_read_data;
    logic       mem_cycle_active;
    upd7220_pkg::memory_cycle_kind_t unused_mem_cycle_kind;
    upd7220_pkg::memory_cycle_phase_t unused_mem_cycle_phase;
    logic       unused_rmw_read_data_valid;
    logic [15:0] unused_rmw_read_data;
    logic       mem_display_request_valid;
    logic       mem_display_accept;

    assign _unused_inputs = ^{
        v_ext_sync_i,
        dack_n,
        mem_ad_i,
        lpen,
        unused_fifo_read_direction,
        unused_fifo_occupancy,
        unused_command_known,
        unused_started_parameter_limit,
        parameter_opcode[7:4],
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
        unused_framing_mode,
        unused_refresh_enable,
        unused_drawing_during_retrace_only,
        unused_horizontal_blank,
        unused_horizontal_phase,
        unused_horizontal_word_index,
        unused_field_start,
        unused_vertical_phase,
        unused_vertical_line_index,
        unused_ead,
        unused_dot_address,
        unused_mask,
        unused_pram_programmed_mask,
        unused_partition_index,
        unused_partition_line_index,
        unused_partition_line_count,
        unused_character_scanline,
        unused_partition_start_address,
        unused_image_area,
        unused_graphics_area,
        unused_wide_access,
        unused_mem_response_kind,
        unused_mem_cycle_kind,
        unused_mem_cycle_phase,
        unused_rmw_read_data_valid,
        unused_rmw_read_data,
        mem_response_valid,
        mem_response_address,
        mem_response_read_data,
        mem_cycle_active
    };

    // START begins raster display-memory scanning. BCTRL/SYNC DE controls
    // video blanking but does not return the device to idle, so fetches keep
    // their cadence while blanked. Character/mixed pin multiplexing is added
    // with those mode milestones; only graphics requests reach the raw 18-bit
    // primitive until then.
    assign mem_display_request_valid = !idle_q
        && raster_partition_active
        && timing_active_word
        && (sync_display_mode == upd7220_pkg::DISPLAY_GRAPHICS);
    assign mem_display_accept = mem_display_request_valid && mem_request_ready;

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
        .turn_to_read              (cursor_turn_to_read),
        .response_valid            (cursor_response_valid),
        .response_data             (cursor_response_data),
        .response_ready            (fifo_response_ready),
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
        .parameter_opcode,
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
        .display_mode              (sync_display_mode),
        .framing_mode              (unused_framing_mode),
        .refresh_enable            (unused_refresh_enable),
        .drawing_during_retrace_only (unused_drawing_during_retrace_only),
        .active_words              (sync_active_words),
        .hsync_width               (sync_hsync_width),
        .vsync_width               (sync_vsync_width),
        .horizontal_front_porch    (sync_horizontal_front_porch),
        .horizontal_back_porch     (sync_horizontal_back_porch),
        .vertical_front_porch      (sync_vertical_front_porch),
        .active_lines              (sync_active_lines),
        .vertical_back_porch       (sync_vertical_back_porch)
    );

    upd7220_pitch #(
        .GDC_VARIANT
    ) pitch_register (
        .clk_2x,
        .integration_reset_n,
        .parameter_valid,
        .parameter_kind,
        .parameter_index,
        .parameter_data,
        .pitch                      (display_pitch)
    );

    upd7220_cursor cursor_registers (
        .clk_2x,
        .integration_reset_n,
        .reset_command,
        .command_start,
        .started_kind,
        .parameter_valid,
        .parameter_kind,
        .parameter_index,
        .parameter_data,
        .turn_to_read               (cursor_turn_to_read),
        .response_valid             (cursor_response_valid),
        .response_data              (cursor_response_data),
        .response_ready             (fifo_response_ready),
        .ead                         (unused_ead),
        .dot_address                 (unused_dot_address),
        .mask                        (unused_mask)
    );

    upd7220_pram parameter_ram_registers (
        .clk_2x,
        .integration_reset_n,
        .reset_command,
        .parameter_valid,
        .parameter_kind,
        .start_address                 (parameter_opcode[3:0]),
        .parameter_index,
        .parameter_data,
        .parameter_ram               (display_parameter_ram),
        .programmed_mask             (unused_pram_programmed_mask)
    );

    upd7220_partitions display_partitions (
        .clk_2x,
        .integration_reset_n,
        .reset_command,
        .display_mode                 (sync_display_mode),
        .pitch                        (display_pitch),
        // CCHAR supplies the actual row height in Milestone 34. A value of
        // one preserves correct graphics and one-scanline character behavior.
        .lines_per_character_row      (6'd1),
        .parameter_ram                (display_parameter_ram),
        .active_line                  (timing_active_line),
        .line_start                   (timing_line_start),
        .display_advance              (mem_display_accept),
        .partition_active             (raster_partition_active),
        .partition_index              (unused_partition_index),
        .partition_line_index         (unused_partition_line_index),
        .partition_line_count         (unused_partition_line_count),
        .character_scanline           (unused_character_scanline),
        .partition_start_address      (unused_partition_start_address),
        .dad                          (raster_dad),
        .image_area                   (unused_image_area),
        .graphics_area                (unused_graphics_area),
        .wide_access                  (unused_wide_access)
    );

    // Graphics raster fetches own the primitive in this milestone. Refresh,
    // drawing, DMA, and mode-specific display schedulers join through explicit
    // arbitration in their dedicated milestones.
    upd7220_memif memory_interface (
        .clk_2x,
        .integration_reset_n,
        .reset_command,
        .request_valid                (mem_display_request_valid),
        .request_ready                (mem_request_ready),
        .request_kind                 (upd7220_pkg::MEM_CYCLE_DISPLAY),
        .request_address              (raster_dad),
        .rmw_write_data               (16'h0000),
        .response_valid               (mem_response_valid),
        .response_kind                (unused_mem_response_kind),
        .response_address             (mem_response_address),
        .response_read_data           (mem_response_read_data),
        .cycle_active                 (mem_cycle_active),
        .cycle_kind                   (unused_mem_cycle_kind),
        .cycle_phase                  (unused_mem_cycle_phase),
        .rmw_read_data_valid          (unused_rmw_read_data_valid),
        .rmw_read_data                (unused_rmw_read_data),
        .mem_ad_i,
        .mem_ad_o,
        .mem_ad_oe,
        .mem_a16,
        .mem_a17,
        .mem_ale,
        .mem_dbin_n
    );

    upd7220_video_timing video_timing (
        .clk_2x,
        .integration_reset_n,
        .reset_command,
        .word_time_ce,
        .display_enable             (sync_display_enable && !idle_q),
        .active_words               (sync_active_words),
        .hsync_width                (sync_hsync_width),
        .horizontal_front_porch     (sync_horizontal_front_porch),
        .horizontal_back_porch      (sync_horizontal_back_porch),
        .vertical_blank             (timing_vertical_blank),
        .hsync,
        .horizontal_blank           (unused_horizontal_blank),
        .blank,
        .active_word                (timing_active_word),
        .line_start                 (timing_line_start),
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
        .active_line                (timing_active_line),
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
            drq          <= 1'b0;
        end else if (reset_command) begin
            device_initialized_q <= 1'b1;
            idle_q               <= 1'b1;
            word_half_q          <= 1'b0;
            word_time_ce         <= 1'b0;
            drq                  <= 1'b0;
        end else begin
            word_half_q  <= ~word_half_q;
            word_time_ce <= word_half_q;
            if (command_start && (started_kind == upd7220_pkg::CMD_START)) begin
                idle_q <= 1'b0;
            end
        end
    end

endmodule

`default_nettype wire
