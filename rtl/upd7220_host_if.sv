`default_nettype none

module upd7220_host_if (
    input  logic       clk_2x,
    input  logic       integration_reset_n,

    input  logic       host_rd_n,
    input  logic       host_wr_n,
    input  logic       host_a0,
    input  logic [7:0] host_db_i,
    output logic [7:0] host_db_o,
    output logic       host_db_oe,

    input  logic [7:0] status_i,
    input  logic [7:0] fifo_read_data_i,

    output logic       fifo_write_valid,
    output logic       fifo_write_is_command,
    output logic [7:0] fifo_write_data,
    output logic       fifo_read_pop
);

    logic [7:0] read_data_q;
    logic [7:0] write_data_host_q;
    logic       write_is_command_host_q;
    logic       read_is_fifo_host_q;
    logic       write_toggle_host_q;
    logic       read_toggle_host_q;

    (* ASYNC_REG = "TRUE" *) logic write_toggle_meta_q;
    (* ASYNC_REG = "TRUE" *) logic write_toggle_sync_q;
    (* ASYNC_REG = "TRUE" *) logic read_toggle_meta_q;
    (* ASYNC_REG = "TRUE" *) logic read_toggle_sync_q;
    logic write_toggle_seen_q;
    logic read_toggle_seen_q;

    // RD falling captures the selected source in the host-interface data
    // register. Holding this register makes DB stable for the whole RD pulse.
    always_ff @(negedge host_rd_n or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            read_data_q         <= 8'h00;
            read_is_fifo_host_q <= 1'b0;
        end else if (host_a0) begin
            read_data_q         <= fifo_read_data_i;
            read_is_fifo_host_q <= 1'b1;
        end else begin
            read_data_q         <= status_i;
            read_is_fifo_host_q <= 1'b0;
        end
    end

    assign host_db_o = read_data_q;
    assign host_db_oe = !host_rd_n;

    // A0 is selected at the leading edge of WR; host data is captured at the
    // trailing edge after its documented setup interval.
    always_ff @(negedge host_wr_n or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            write_is_command_host_q <= 1'b0;
        end else begin
            write_is_command_host_q <= host_a0;
        end
    end

    // Captured data and tag remain stable while the toggle is synchronized.
    always_ff @(posedge host_wr_n or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            write_data_host_q   <= 8'h00;
            write_toggle_host_q <= 1'b0;
        end else begin
            write_data_host_q   <= host_db_i;
            write_toggle_host_q <= ~write_toggle_host_q;
        end
    end

    // Only FIFO reads have a side effect. Status reads never advance the FIFO.
    always_ff @(posedge host_rd_n or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            read_toggle_host_q <= 1'b0;
        end else if (read_is_fifo_host_q) begin
            read_toggle_host_q <= ~read_toggle_host_q;
        end
    end

    always_ff @(posedge clk_2x or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            write_toggle_meta_q <= 1'b0;
            write_toggle_sync_q <= 1'b0;
            write_toggle_seen_q <= 1'b0;
            read_toggle_meta_q  <= 1'b0;
            read_toggle_sync_q  <= 1'b0;
            read_toggle_seen_q  <= 1'b0;
        end else begin
            write_toggle_meta_q <= write_toggle_host_q;
            write_toggle_sync_q <= write_toggle_meta_q;
            read_toggle_meta_q  <= read_toggle_host_q;
            read_toggle_sync_q  <= read_toggle_meta_q;
            if (fifo_write_valid) begin
                write_toggle_seen_q <= write_toggle_sync_q;
            end
            if (fifo_read_pop) begin
                read_toggle_seen_q <= read_toggle_sync_q;
            end
        end
    end

    assign fifo_write_valid = write_toggle_sync_q ^ write_toggle_seen_q;
    assign fifo_write_is_command = write_is_command_host_q;
    assign fifo_write_data = write_data_host_q;
    assign fifo_read_pop = read_toggle_sync_q ^ read_toggle_seen_q;

`ifndef SYNTHESIS
    property p_host_strobes_do_not_overlap;
        @(posedge clk_2x) disable iff (!integration_reset_n)
            !(!host_rd_n && !host_wr_n);
    endproperty

    assert property (p_host_strobes_do_not_overlap)
        else $error("simultaneous RD and WR is outside documented host operation");
`endif

endmodule

`default_nettype wire
