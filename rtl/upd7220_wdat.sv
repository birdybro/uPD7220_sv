`default_nettype none

// Initial WDAT execution slice: TT=word, MOD=replace, one RMW cycle for each
// complete low/high parameter group. FIGS-driven repetition, byte formats,
// other logical operations, and nonzero drawing directions extend this block
// in the following milestones.
module upd7220_wdat (
    input  logic                              clk_2x,
    input  logic                              integration_reset_n,
    input  logic                              reset_command,

    input  logic                              parameter_valid,
    input  upd7220_pkg::command_kind_t        parameter_kind,
    input  logic [7:0]                        parameter_opcode,
    input  logic [3:0]                        parameter_index,
    input  logic [7:0]                        parameter_data,

    input  upd7220_pkg::display_mode_t        display_mode,
    input  logic [17:0]                       cursor_ead,
    input  logic [15:0]                       cursor_mask,
    input  logic [8:0]                        pitch,

    output logic                              busy,
    output logic [15:0]                       pattern,
    output logic                              request_valid,
    input  logic                              request_ready,
    output logic [17:0]                       request_address,
    output logic [15:0]                       rmw_write_data,

    input  logic                              response_valid,
    input  upd7220_pkg::memory_cycle_kind_t  response_kind,
    input  logic [17:0]                       response_address,
    input  logic                              rmw_read_data_valid,
    input  logic [15:0]                       rmw_read_data,

    output logic                              cursor_update_valid,
    output logic [17:0]                       cursor_update_ead
);

    logic [15:0] pattern_q;
    logic [7:0]  low_byte_q;
    logic [15:0] operation_pattern_q;
    logic [15:0] operation_mask_q;
    logic [17:0] operation_address_q;
    logic        pending_q;
    logic        active_q;
    logic        read_seen_q;

    logic supported_parameter_group;
    logic request_accept;
    logic response_accept;

    assign supported_parameter_group = parameter_valid
        && (parameter_kind == upd7220_pkg::CMD_WDAT)
        && (parameter_opcode == 8'h20)
        && (parameter_index == 4'd1);
    assign busy = pending_q || active_q;
    assign pattern = pattern_q;
    assign request_valid = pending_q;
    assign request_accept = request_valid && request_ready;
    assign request_address = operation_address_q;
    assign rmw_write_data = (rmw_read_data & ~operation_mask_q)
        | (operation_pattern_q & operation_mask_q);
    assign response_accept = active_q && response_valid
        && (response_kind == upd7220_pkg::MEM_CYCLE_RMW)
        && (response_address == operation_address_q);
    assign cursor_update_valid = response_accept;
    // The implemented basic subset is FIGS DIR=0: straight down by pitch.
    assign cursor_update_ead = operation_address_q + {{9{1'b0}}, pitch};

    always_ff @(posedge clk_2x or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            pattern_q           <= 16'h0000;
            low_byte_q          <= 8'h00;
            operation_pattern_q <= 16'h0000;
            operation_mask_q    <= 16'h0000;
            operation_address_q <= 18'h00000;
            pending_q           <= 1'b0;
            active_q            <= 1'b0;
            read_seen_q         <= 1'b0;
        end else if (reset_command) begin
            // RESET aborts execution but retains the programmer-loaded Pattern
            // register along with the other drawing parameters.
            low_byte_q <= 8'h00;
            pending_q  <= 1'b0;
            active_q   <= 1'b0;
            read_seen_q <= 1'b0;
        end else begin
            if (parameter_valid
                && (parameter_kind == upd7220_pkg::CMD_WDAT)
                && (parameter_index == 4'd0)) begin
                low_byte_q    <= parameter_data;
                pattern_q[7:0] <= parameter_data;
            end

            if (supported_parameter_group) begin
                pattern_q[15:8]    <= parameter_data;
                operation_pattern_q <=
                    (display_mode == upd7220_pkg::DISPLAY_GRAPHICS)
                    ? {16{low_byte_q[0]}}
                    : {parameter_data, low_byte_q};
                operation_mask_q    <= cursor_mask;
                operation_address_q <= cursor_ead;
                pending_q           <= 1'b1;
            end

            if (request_accept) begin
                pending_q <= 1'b0;
                active_q  <= 1'b1;
                read_seen_q <= 1'b0;
            end

            if (active_q && rmw_read_data_valid) begin
                read_seen_q <= 1'b1;
            end

            if (response_accept) begin
                active_q <= 1'b0;
                read_seen_q <= 1'b0;
            end
        end
    end

`ifndef SYNTHESIS
    property p_no_second_group_while_busy;
        @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
            supported_parameter_group |-> !busy;
    endproperty
    property p_request_is_pending;
        @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
            request_valid |-> pending_q;
    endproperty
    property p_response_follows_read;
        @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
            response_accept |-> read_seen_q;
    endproperty
    property p_response_updates_cursor;
        @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
            response_accept |-> cursor_update_valid;
    endproperty

    assert property (p_no_second_group_while_busy)
        else $error("WDAT accepted another parameter group while busy");
    assert property (p_request_is_pending)
        else $error("WDAT requested memory without a pending data group");
    assert property (p_response_follows_read)
        else $error("WDAT completed without observing its RMW read phase");
    assert property (p_response_updates_cursor)
        else $error("completed WDAT did not request an EAD update");
`endif

endmodule

`default_nettype wire
