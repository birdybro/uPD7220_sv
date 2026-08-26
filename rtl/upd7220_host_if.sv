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
    output logic       fifo_read_pop,
    output logic       reset_command
);

    // Reset request/acknowledge deliberately crosses between asynchronous WR
    // and 2xWCLK and is used to recover the ordinary event synchronizers.
    /* verilator lint_off SYNCASYNCNET */

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
    logic write_event;
    logic reset_request_host_q;
    (* ASYNC_REG = "TRUE" *) logic reset_request_meta_q;
    (* ASYNC_REG = "TRUE" *) logic reset_request_sync_q;
    logic host_event_reset_n;
    logic cdc_event_reset_n;

    assign host_event_reset_n = integration_reset_n
        && !reset_request_host_q && !reset_request_sync_q;
    assign cdc_event_reset_n = integration_reset_n && !reset_request_sync_q;

    // RD falling captures the selected source in the host-interface data
    // register. Holding this register makes DB stable for the whole RD pulse.
    always_ff @(negedge host_rd_n or negedge host_event_reset_n) begin
        if (!host_event_reset_n) begin
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
    always_ff @(negedge host_wr_n or negedge host_event_reset_n) begin
        if (!host_event_reset_n) begin
            write_is_command_host_q <= 1'b0;
        end else begin
            write_is_command_host_q <= host_a0;
        end
    end

    // Captured data and tag remain stable while the toggle is synchronized.
    always_ff @(posedge host_wr_n or negedge host_event_reset_n) begin
        if (!host_event_reset_n) begin
            write_data_host_q   <= 8'h00;
            write_toggle_host_q <= 1'b0;
        end else begin
            write_data_host_q   <= host_db_i;
            write_toggle_host_q <= ~write_toggle_host_q;
        end
    end

    // Only FIFO reads have a side effect. Status reads never advance the FIFO.
    always_ff @(posedge host_rd_n or negedge host_event_reset_n) begin
        if (!host_event_reset_n) begin
            read_toggle_host_q <= 1'b0;
        end else if (read_is_fifo_host_q) begin
            read_toggle_host_q <= ~read_toggle_host_q;
        end
    end

    // Unlike ordinary writes, the first RESET must recover even when the CDC
    // event toggles powered up unknown. A level request is forced high by the
    // trailing WR edge and cleared only after its synchronized acknowledgement.
    always_ff @(posedge host_wr_n or negedge integration_reset_n
               or posedge reset_request_sync_q) begin
        if (!integration_reset_n) begin
            reset_request_host_q <= 1'b0;
        end else if (reset_request_sync_q) begin
            reset_request_host_q <= 1'b0;
        end else if (write_is_command_host_q && (host_db_i == 8'h00)) begin
            reset_request_host_q <= 1'b1;
        end
    end

    // This synchronizer is deliberately independent of the state it resets.
    // Sampling a level eventually produces a known reset even from unknown
    // power-up contents; the host request is held until acknowledgement.
    always_ff @(posedge clk_2x or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            reset_request_meta_q <= 1'b0;
            reset_request_sync_q <= 1'b0;
        end else begin
            reset_request_meta_q <= reset_request_host_q;
            reset_request_sync_q <= reset_request_meta_q;
        end
    end

    always_ff @(posedge clk_2x or negedge cdc_event_reset_n) begin
        if (!cdc_event_reset_n) begin
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
            if (write_event) begin
                write_toggle_seen_q <= write_toggle_sync_q;
            end
            if (fifo_read_pop) begin
                read_toggle_seen_q <= read_toggle_sync_q;
            end
        end
    end

    assign write_event = write_toggle_sync_q ^ write_toggle_seen_q;
    assign fifo_write_is_command = write_is_command_host_q;
    assign fifo_write_data = write_data_host_q;
    assign fifo_read_pop = read_toggle_sync_q ^ read_toggle_seen_q;
    // RESET has dedicated decode hardware ahead of the FIFO and never occupies
    // a FIFO location. The synchronized level lasts until the host-domain
    // request observes acknowledgement.
    assign reset_command = reset_request_sync_q;
    assign fifo_write_valid = write_event;

`ifndef SYNTHESIS
    property p_host_strobes_do_not_overlap;
        @(posedge clk_2x) disable iff (!integration_reset_n)
            !(!host_rd_n && !host_wr_n);
    endproperty
    property p_reset_bypasses_fifo;
        @(posedge clk_2x) disable iff (!integration_reset_n)
            reset_command |-> !fifo_write_valid;
    endproperty

    assert property (p_host_strobes_do_not_overlap)
        else $error("simultaneous RD and WR is outside documented host operation");
    assert property (p_reset_bypasses_fifo)
        else $error("RESET opcode was also written into the FIFO");
`endif

    /* verilator lint_on SYNCASYNCNET */

endmodule

`default_nettype wire
