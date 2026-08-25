`default_nettype none

module upd7220_fifo (
    input  logic       clk_2x,
    input  logic       integration_reset_n,
    input  logic       fifo_reset,

    input  logic       host_write_valid,
    input  logic       host_write_is_command,
    input  logic [7:0] host_write_data,
    input  logic       host_read_pop,

    output logic       command_valid,
    output logic       command_is_command,
    output logic [7:0] command_data,
    input  logic       command_pop,
    input  logic       turn_to_read,

    input  logic       response_valid,
    input  logic [7:0] response_data,
    output logic       response_ready,

    output logic [7:0] host_read_data,
    output logic       fifo_empty,
    output logic       fifo_full,
    output logic       data_ready,
    output logic       read_direction,
    output logic [4:0] occupancy
);

    typedef struct packed {
        logic       is_command;
        logic [7:0] data;
    } fifo_entry_t;

    fifo_entry_t storage [0:upd7220_pkg::FIFO_DEPTH-1];
    logic [3:0] read_pointer_q;
    logic [3:0] write_pointer_q;
    logic [4:0] occupancy_q;
    logic       read_direction_q;
    logic [7:0] data_register_q;
    logic       data_register_valid_q;
    logic [2:0] refill_count_q;

    assign occupancy = occupancy_q;
    assign read_direction = read_direction_q;
    assign fifo_empty = occupancy_q == 5'd0;
    assign fifo_full = occupancy_q == 5'd16;
    assign data_ready = read_direction_q && data_register_valid_q;
    assign host_read_data = data_register_q;

    assign command_valid = !read_direction_q && (occupancy_q != 5'd0);
    assign command_is_command = storage[read_pointer_q].is_command;
    assign command_data = storage[read_pointer_q].data;

    // A refill completing this edge owns the ring RAM read port. The response
    // producer retains its byte until ready returns high on the next edge.
    assign response_ready = read_direction_q
        && (occupancy_q != 5'd16)
        && (refill_count_q != 3'd1)
        && !turn_to_read;

    always_ff @(posedge clk_2x or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            read_pointer_q         <= 4'h0;
            write_pointer_q        <= 4'h0;
            occupancy_q            <= 5'd0;
            read_direction_q       <= 1'b0;
            data_register_q        <= 8'h00;
            data_register_valid_q  <= 1'b0;
            refill_count_q         <= 3'd0;
        end else if (fifo_reset) begin
            read_pointer_q         <= 4'h0;
            write_pointer_q        <= 4'h0;
            occupancy_q            <= 5'd0;
            read_direction_q       <= 1'b0;
            data_register_q        <= 8'h00;
            data_register_valid_q  <= 1'b0;
            refill_count_q         <= 3'd0;
        end else if (read_direction_q && host_write_valid
                     && host_write_is_command) begin
            // A command aborts unread data even when the read FIFO is full.
            storage[0]             <= '{is_command: 1'b1, data: host_write_data};
            read_pointer_q         <= 4'h0;
            write_pointer_q        <= 4'h1;
            occupancy_q            <= 5'd1;
            read_direction_q       <= 1'b0;
            data_register_valid_q  <= 1'b0;
            refill_count_q         <= 3'd0;
        end else if (turn_to_read) begin
            // Every direction turnaround completely empties the ring and the
            // separate host data register.
            read_pointer_q         <= 4'h0;
            write_pointer_q        <= 4'h0;
            occupancy_q            <= 5'd0;
            read_direction_q       <= 1'b1;
            data_register_valid_q  <= 1'b0;
            refill_count_q         <= 3'd0;
        end else if (!read_direction_q) begin
            // Host access has priority over a simultaneous command-processor
            // ring access. A seventeenth write overwrites the oldest byte.
            if (host_write_valid) begin
                storage[write_pointer_q] <= '{
                    is_command: host_write_is_command,
                    data: host_write_data
                };
                write_pointer_q <= write_pointer_q + 4'd1;
                if (occupancy_q == 5'd16) begin
                    read_pointer_q <= read_pointer_q + 4'd1;
                end else begin
                    occupancy_q <= occupancy_q + 5'd1;
                end
            end else if (command_pop && command_valid) begin
                read_pointer_q <= read_pointer_q + 4'd1;
                occupancy_q <= occupancy_q - 5'd1;
            end
        end else begin
            // Reading the host data register clears DATA READY. If ring data is
            // waiting, the next register load completes four 2xWCLK edges later.
            if (host_read_pop && data_register_valid_q) begin
                data_register_valid_q <= 1'b0;
                if (occupancy_q != 5'd0) begin
                    refill_count_q <= 3'd4;
                end
            end else if (!data_register_valid_q) begin
                if (refill_count_q == 3'd1) begin
                    data_register_q       <= storage[read_pointer_q].data;
                    data_register_valid_q <= 1'b1;
                    read_pointer_q        <= read_pointer_q + 4'd1;
                    occupancy_q           <= occupancy_q - 5'd1;
                    refill_count_q        <= 3'd0;
                end else if (refill_count_q != 3'd0) begin
                    refill_count_q <= refill_count_q - 3'd1;
                end else if (occupancy_q != 5'd0) begin
                    refill_count_q <= 3'd4;
                end
            end

            if (response_valid && response_ready) begin
                storage[write_pointer_q] <= '{is_command: 1'b0, data: response_data};
                write_pointer_q <= write_pointer_q + 4'd1;
                occupancy_q <= occupancy_q + 5'd1;
                if (!data_register_valid_q && (occupancy_q == 5'd0)
                    && (refill_count_q == 3'd0)) begin
                    refill_count_q <= 3'd4;
                end
            end
        end
    end

`ifndef SYNTHESIS
    property p_occupancy_in_range;
        @(posedge clk_2x) occupancy_q <= 5'd16;
    endproperty
    property p_no_command_underflow;
        @(posedge clk_2x) disable iff (!integration_reset_n || fifo_reset)
            command_pop |-> command_valid;
    endproperty
    property p_no_host_read_underflow;
        @(posedge clk_2x) disable iff (!integration_reset_n || fifo_reset)
            host_read_pop |-> data_ready;
    endproperty
    property p_response_honors_backpressure;
        @(posedge clk_2x) disable iff (!integration_reset_n || fifo_reset)
            response_valid |-> response_ready;
    endproperty
    property p_parameter_cannot_abort_read_mode;
        @(posedge clk_2x) disable iff (!integration_reset_n || fifo_reset)
            (read_direction_q && host_write_valid) |-> host_write_is_command;
    endproperty

    assert property (p_occupancy_in_range)
        else $error("FIFO occupancy exceeded 16 entries");
    assert property (p_no_command_underflow)
        else $error("command processor popped an unavailable FIFO entry");
    assert property (p_no_host_read_underflow)
        else $error("host read occurred without DATA READY");
    assert property (p_response_honors_backpressure)
        else $error("response producer ignored FIFO backpressure");
    assert property (p_parameter_cannot_abort_read_mode)
        else $error("only a command byte can terminate FIFO read mode");
`endif

endmodule

`default_nettype wire
