`default_nettype none

module upd7220_command (
    input  logic                        clk_2x,
    input  logic                        integration_reset_n,
    input  logic                        command_reset,
    input  logic                        processor_enable,

    input  logic                        fifo_valid,
    input  logic                        fifo_is_command,
    input  logic [7:0]                  fifo_data,
    output logic                        fifo_pop,

    output logic                        command_start,
    output logic                        command_known,
    output upd7220_pkg::command_kind_t  started_kind,
    output logic [7:0]                  started_opcode,
    output logic [4:0]                  started_parameter_limit,

    output logic                        parameter_valid,
    output logic [7:0]                  parameter_data,
    output logic [3:0]                  parameter_index,
    output upd7220_pkg::command_kind_t  parameter_kind,
    output logic [7:0]                  parameter_opcode,

    output logic                        command_complete,
    output logic [7:0]                  completed_opcode,
    output logic                        command_interrupted,
    output logic [7:0]                  interrupted_opcode,
    output logic                        unexpected_parameter,

    output logic                        command_active,
    output upd7220_pkg::command_kind_t  active_kind,
    output logic [7:0]                  active_opcode,
    output logic [3:0]                  next_parameter_index
);

    upd7220_pkg::command_kind_t active_kind_q;
    logic [7:0] active_opcode_q;
    logic [4:0] active_parameter_limit_q;
    logic [3:0] next_parameter_index_q;
    logic       command_active_q;

    upd7220_pkg::command_kind_t decoded_kind;
    logic [4:0] decoded_parameter_limit;

    assign decoded_kind = upd7220_pkg::decode_command(fifo_data);
    assign decoded_parameter_limit =
        upd7220_pkg::command_parameter_limit(decoded_kind, fifo_data[4:0]);

    assign fifo_pop = processor_enable && fifo_valid;
    assign command_active = command_active_q;
    assign active_kind = active_kind_q;
    assign active_opcode = active_opcode_q;
    assign next_parameter_index = next_parameter_index_q;

    always_ff @(posedge clk_2x or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            command_start             <= 1'b0;
            command_known             <= 1'b0;
            started_kind              <= upd7220_pkg::CMD_INVALID;
            started_opcode            <= 8'h00;
            started_parameter_limit   <= 5'd0;
            parameter_valid           <= 1'b0;
            parameter_data            <= 8'h00;
            parameter_index           <= 4'd0;
            parameter_kind            <= upd7220_pkg::CMD_INVALID;
            parameter_opcode          <= 8'h00;
            command_complete          <= 1'b0;
            completed_opcode          <= 8'h00;
            command_interrupted       <= 1'b0;
            interrupted_opcode        <= 8'h00;
            unexpected_parameter      <= 1'b0;
            command_active_q          <= 1'b0;
            active_kind_q             <= upd7220_pkg::CMD_INVALID;
            active_opcode_q           <= 8'h00;
            active_parameter_limit_q  <= 5'd0;
            next_parameter_index_q    <= 4'd0;
        end else if (command_reset) begin
            command_start             <= 1'b0;
            command_known             <= 1'b0;
            parameter_valid           <= 1'b0;
            command_complete          <= 1'b0;
            command_interrupted       <= 1'b0;
            unexpected_parameter      <= 1'b0;
            command_active_q          <= 1'b0;
            active_kind_q             <= upd7220_pkg::CMD_INVALID;
            active_parameter_limit_q  <= 5'd0;
            next_parameter_index_q    <= 4'd0;
        end else begin
            command_start        <= 1'b0;
            command_known        <= 1'b0;
            parameter_valid      <= 1'b0;
            command_complete     <= 1'b0;
            command_interrupted  <= 1'b0;
            unexpected_parameter <= 1'b0;

            if (fifo_pop) begin
                if (fifo_is_command) begin
                    if (command_active_q) begin
                        command_interrupted <= 1'b1;
                        interrupted_opcode  <= active_opcode_q;
                    end

                    command_start           <= 1'b1;
                    command_known           <= decoded_kind != upd7220_pkg::CMD_INVALID;
                    started_kind            <= decoded_kind;
                    started_opcode          <= fifo_data;
                    started_parameter_limit <= decoded_parameter_limit;
                    active_kind_q           <= decoded_kind;
                    active_opcode_q         <= fifo_data;
                    active_parameter_limit_q <= decoded_parameter_limit;
                    next_parameter_index_q  <= 4'd0;

                    if ((decoded_kind == upd7220_pkg::CMD_INVALID)
                        || (decoded_parameter_limit == 5'd0)) begin
                        command_active_q <= 1'b0;
                        if (decoded_kind != upd7220_pkg::CMD_INVALID) begin
                            command_complete <= 1'b1;
                            completed_opcode <= fifo_data;
                        end
                    end else begin
                        command_active_q <= 1'b1;
                    end
                end else if (command_active_q) begin
                    parameter_valid  <= 1'b1;
                    parameter_data   <= fifo_data;
                    parameter_index  <= next_parameter_index_q;
                    parameter_kind   <= active_kind_q;
                    parameter_opcode <= active_opcode_q;

                    if (upd7220_pkg::command_repeats_parameter_group(active_kind_q)) begin
                        if ({1'b0, next_parameter_index_q} + 5'd1
                            == active_parameter_limit_q) begin
                            next_parameter_index_q <= 4'd0;
                        end else begin
                            next_parameter_index_q <= next_parameter_index_q + 4'd1;
                        end
                    end else if ({1'b0, next_parameter_index_q} + 5'd1
                                 == active_parameter_limit_q) begin
                        command_active_q       <= 1'b0;
                        next_parameter_index_q <= 4'd0;
                        command_complete       <= 1'b1;
                        completed_opcode       <= active_opcode_q;
                    end else begin
                        next_parameter_index_q <= next_parameter_index_q + 4'd1;
                    end
                end else begin
                    unexpected_parameter <= 1'b1;
                end
            end
        end
    end

`ifndef SYNTHESIS
    property p_parameter_index_in_range;
        @(posedge clk_2x) disable iff (!integration_reset_n || command_reset)
            command_active_q |->
                ({1'b0, next_parameter_index_q} < active_parameter_limit_q);
    endproperty
    property p_pop_only_available_entry;
        @(posedge clk_2x) disable iff (!integration_reset_n || command_reset)
            fifo_pop |-> fifo_valid;
    endproperty
    property p_parameter_event_has_active_command;
        @(posedge clk_2x) disable iff (!integration_reset_n || command_reset)
            parameter_valid |-> (parameter_kind != upd7220_pkg::CMD_INVALID);
    endproperty

    assert property (p_parameter_index_in_range)
        else $error("command parameter index exceeded its documented limit");
    assert property (p_pop_only_available_entry)
        else $error("command parser popped an unavailable FIFO entry");
    assert property (p_parameter_event_has_active_command)
        else $error("parameter event has no decoded command");
`endif

endmodule

`default_nettype wire
