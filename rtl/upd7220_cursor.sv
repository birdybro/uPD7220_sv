`default_nettype none

module upd7220_cursor (
    input  logic                       clk_2x,
    input  logic                       integration_reset_n,
    input  logic                       reset_command,

    input  logic                       command_start,
    input  upd7220_pkg::command_kind_t started_kind,
    input  logic                       parameter_valid,
    input  upd7220_pkg::command_kind_t parameter_kind,
    input  logic [3:0]                 parameter_index,
    input  logic [7:0]                 parameter_data,

    input  logic                       execution_ead_update_valid,
    input  logic [17:0]                execution_ead_update,

    output logic                       turn_to_read,
    output logic                       response_valid,
    output logic [7:0]                 response_data,
    input  logic                       response_ready,

    output logic [17:0]                ead,
    output logic [3:0]                 dot_address,
    output logic [15:0]                mask
);

    logic [17:0] ead_q;
    logic [3:0]  dot_address_q;
    logic [15:0] mask_q;
    logic [17:0] response_ead_q;
    logic [15:0] response_mask_q;
    logic [2:0]  response_index_q;
    logic        response_active_q;

    assign ead = ead_q;
    assign dot_address = dot_address_q;
    assign mask = mask_q;

    // Figure 28 requires the FIFO to reverse only after CURD reaches the
    // command processor. The following response is a snapshot of both cursor
    // registers at that command boundary.
    assign turn_to_read = command_start
        && (started_kind == upd7220_pkg::CMD_CURD);

    // VALID remains asserted with stable data until the FIFO accepts the byte.
    assign response_valid = response_active_q;

    always_comb begin
        unique case (response_index_q)
            3'd0: response_data = response_ead_q[7:0];
            3'd1: response_data = response_ead_q[15:8];
            // Figure 28 marks bits 7:2 undefined. Portable RTL returns zero
            // for them without claiming that value for original silicon.
            3'd2: response_data = {6'b000000, response_ead_q[17:16]};
            3'd3: response_data = response_mask_q[7:0];
            3'd4: response_data = response_mask_q[15:8];
            default: response_data = 8'h00;
        endcase
    end

    always_ff @(posedge clk_2x or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            ead_q             <= 18'h00000;
            dot_address_q     <= 4'h0;
            mask_q            <= 16'h0000;
            response_ead_q    <= 18'h00000;
            response_mask_q   <= 16'h0000;
            response_index_q  <= 3'd0;
            response_active_q <= 1'b0;
        end else begin
            // RESET aborts an in-flight read response but, as with the other
            // programmer-loaded parameters, does not overwrite EAD or MASK.
            if (reset_command) begin
                response_index_q  <= 3'd0;
                response_active_q <= 1'b0;
            end else if (command_start) begin
                if (started_kind == upd7220_pkg::CMD_CURD) begin
                    response_ead_q    <= ead_q;
                    response_mask_q   <= mask_q;
                    response_index_q  <= 3'd0;
                    response_active_q <= 1'b1;
                end else begin
                    response_index_q  <= 3'd0;
                    response_active_q <= 1'b0;
                end
            end else if (response_valid && response_ready) begin
                if (response_index_q == 3'd4) begin
                    response_index_q  <= 3'd0;
                    response_active_q <= 1'b0;
                end else begin
                    response_index_q <= response_index_q + 3'd1;
                end
            end

            if (parameter_valid) begin
                unique case (parameter_kind)
                    upd7220_pkg::CMD_CURS: begin
                        unique case (parameter_index)
                            4'd0: ead_q[7:0]   <= parameter_data;
                            4'd1: ead_q[15:8]  <= parameter_data;
                            4'd2: begin
                                ead_q[17:16]    <= parameter_data[1:0];
                                dot_address_q   <= parameter_data[7:4];
                                mask_q <= 16'h0001 << parameter_data[7:4];
                            end
                            default: begin
                            end
                        endcase
                    end
                    upd7220_pkg::CMD_MASK: begin
                        unique case (parameter_index)
                            4'd0: mask_q[7:0]  <= parameter_data;
                            4'd1: mask_q[15:8] <= parameter_data;
                            default: begin
                            end
                        endcase
                    end
                    default: begin
                    end
                endcase
            end

            if (execution_ead_update_valid) begin
                ead_q <= execution_ead_update;
            end
        end
    end

`ifndef SYNTHESIS
    property p_curd_response_index_in_range;
        @(posedge clk_2x) response_active_q |-> (response_index_q <= 3'd4);
    endproperty
    property p_cursor_mask_is_one_hot;
        @(posedge clk_2x) disable iff (!integration_reset_n)
            (parameter_valid && (parameter_kind == upd7220_pkg::CMD_CURS)
             && (parameter_index == 4'd2)) |=> $onehot(mask_q);
    endproperty
    property p_turnaround_is_curd_only;
        @(posedge clk_2x) turn_to_read |->
            (command_start && (started_kind == upd7220_pkg::CMD_CURD));
    endproperty
    property p_mask_low_byte_load;
        @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
            (parameter_valid && (parameter_kind == upd7220_pkg::CMD_MASK)
             && (parameter_index == 4'd0))
            |=> (mask_q[7:0] == $past(parameter_data));
    endproperty
    property p_mask_high_byte_load;
        @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
            (parameter_valid && (parameter_kind == upd7220_pkg::CMD_MASK)
             && (parameter_index == 4'd1))
            |=> (mask_q[15:8] == $past(parameter_data));
    endproperty
    property p_execution_ead_update;
        @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
            execution_ead_update_valid
            |=> (ead_q == $past(execution_ead_update));
    endproperty

    assert property (p_curd_response_index_in_range)
        else $error("CURD response index exceeded five-byte response");
    assert property (p_cursor_mask_is_one_hot)
        else $error("CURS failed to expand dAD to a one-of-16 mask");
    assert property (p_turnaround_is_curd_only)
        else $error("cursor block requested a non-CURD FIFO turnaround");
    assert property (p_mask_low_byte_load)
        else $error("MASK P1 failed to load the low mask byte");
    assert property (p_mask_high_byte_load)
        else $error("MASK P2 failed to load the high mask byte");
    assert property (p_execution_ead_update)
        else $error("execution engine failed to update EAD");
`endif

endmodule

`default_nettype wire
