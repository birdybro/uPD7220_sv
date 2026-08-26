`default_nettype none

module upd7220_memif (
    input  logic                              clk_2x,
    input  logic                              integration_reset_n,
    input  logic                              reset_command,

    input  logic                              request_valid,
    output logic                              request_ready,
    input  upd7220_pkg::memory_cycle_kind_t  request_kind,
    input  logic [17:0]                       request_address,
    input  logic [15:0]                       rmw_write_data,

    output logic                              response_valid,
    output upd7220_pkg::memory_cycle_kind_t  response_kind,
    output logic [17:0]                       response_address,
    output logic [15:0]                       response_read_data,

    output logic                              cycle_active,
    output upd7220_pkg::memory_cycle_kind_t  cycle_kind,
    output upd7220_pkg::memory_cycle_phase_t cycle_phase,
    output logic                              rmw_read_data_valid,
    output logic [15:0]                       rmw_read_data,

    input  logic [15:0]                       mem_ad_i,
    output logic [15:0]                       mem_ad_o,
    output logic                              mem_ad_oe,
    output logic                              mem_a16,
    output logic                              mem_a17,
    output logic                              mem_ale,
    output logic                              mem_dbin_n
);

    upd7220_pkg::memory_cycle_phase_t phase_q;
    upd7220_pkg::memory_cycle_kind_t kind_q;
    logic [17:0] address_q;
    logic [15:0] read_data_q;
    logic [15:0] write_data_q;
    logic response_valid_q;
    upd7220_pkg::memory_cycle_kind_t response_kind_q;
    logic [17:0] response_address_q;
    logic [15:0] response_read_data_q;

    // ALE rises with a cycle-starting positive edge and falls with the first
    // negative edge. Separate epoch and acknowledgement flops model those two
    // documented edges without a dual-edge procedural block or a #delay.
    logic ale_epoch_q;
    logic ale_fall_epoch_q;
    logic dbin_n_q;

    logic final_phase;
    logic accept_request;

    assign cycle_active = phase_q != upd7220_pkg::MEM_PHASE_IDLE;
    assign cycle_kind = kind_q;
    assign cycle_phase = phase_q;
    assign final_phase =
        ((kind_q == upd7220_pkg::MEM_CYCLE_DISPLAY)
         && (phase_q == upd7220_pkg::MEM_PHASE_C2))
        || ((kind_q == upd7220_pkg::MEM_CYCLE_RMW)
            && (phase_q == upd7220_pkg::MEM_PHASE_C4));
    assign request_ready = !cycle_active || final_phase;
    assign accept_request = request_valid && request_ready;

    assign response_valid = response_valid_q;
    assign response_kind = response_kind_q;
    assign response_address = response_address_q;
    assign response_read_data = response_read_data_q;
    assign rmw_read_data_valid =
        (kind_q == upd7220_pkg::MEM_CYCLE_RMW)
        && (phase_q == upd7220_pkg::MEM_PHASE_C4);
    assign rmw_read_data = read_data_q;

    // AD carries the address for all of C1. In RMW C4 it carries the modified
    // write-back data; it is released throughout the intervening read phase.
    assign mem_ad_oe = integration_reset_n && !reset_command
        && ((phase_q == upd7220_pkg::MEM_PHASE_C1)
            || ((kind_q == upd7220_pkg::MEM_CYCLE_RMW)
                && (phase_q == upd7220_pkg::MEM_PHASE_C4)));
    assign mem_ad_o = (phase_q == upd7220_pkg::MEM_PHASE_C4)
        ? write_data_q : address_q[15:0];
    assign mem_a16 = address_q[16];
    assign mem_a17 = address_q[17];
    assign mem_ale = !integration_reset_n || reset_command || !cycle_active
        || (ale_epoch_q != ale_fall_epoch_q);
    assign mem_dbin_n = !integration_reset_n || reset_command || dbin_n_q;

    always_ff @(posedge clk_2x or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            phase_q              <= upd7220_pkg::MEM_PHASE_IDLE;
            kind_q               <= upd7220_pkg::MEM_CYCLE_DISPLAY;
            address_q            <= 18'h00000;
            write_data_q         <= 16'h0000;
            response_valid_q     <= 1'b0;
            response_kind_q      <= upd7220_pkg::MEM_CYCLE_DISPLAY;
            response_address_q   <= 18'h00000;
            response_read_data_q <= 16'h0000;
            ale_epoch_q          <= 1'b0;
        end else if (reset_command) begin
            phase_q              <= upd7220_pkg::MEM_PHASE_IDLE;
            kind_q               <= upd7220_pkg::MEM_CYCLE_DISPLAY;
            address_q            <= 18'h00000;
            write_data_q         <= 16'h0000;
            response_valid_q     <= 1'b0;
            response_kind_q      <= upd7220_pkg::MEM_CYCLE_DISPLAY;
            response_address_q   <= 18'h00000;
            response_read_data_q <= 16'h0000;
            ale_epoch_q          <= 1'b0;
        end else begin
            response_valid_q <= 1'b0;
            unique case (phase_q)
                upd7220_pkg::MEM_PHASE_IDLE: begin
                    if (accept_request) begin
                        kind_q      <= request_kind;
                        address_q   <= request_address;
                        phase_q     <= upd7220_pkg::MEM_PHASE_C1;
                        ale_epoch_q <= ~ale_epoch_q;
                    end
                end
                upd7220_pkg::MEM_PHASE_C1:
                    phase_q <= upd7220_pkg::MEM_PHASE_C2;
                upd7220_pkg::MEM_PHASE_C2: begin
                    if (kind_q == upd7220_pkg::MEM_CYCLE_RMW) begin
                        phase_q <= upd7220_pkg::MEM_PHASE_C3;
                    end else begin
                        response_valid_q     <= 1'b1;
                        response_kind_q      <= kind_q;
                        response_address_q   <= address_q;
                        response_read_data_q <= read_data_q;
                        if (accept_request) begin
                            kind_q      <= request_kind;
                            address_q   <= request_address;
                            phase_q     <= upd7220_pkg::MEM_PHASE_C1;
                            ale_epoch_q <= ~ale_epoch_q;
                        end else begin
                            phase_q <= upd7220_pkg::MEM_PHASE_IDLE;
                        end
                    end
                end
                upd7220_pkg::MEM_PHASE_C3: begin
                    write_data_q <= rmw_write_data;
                    phase_q <= upd7220_pkg::MEM_PHASE_C4;
                end
                upd7220_pkg::MEM_PHASE_C4: begin
                    response_valid_q     <= 1'b1;
                    response_kind_q      <= kind_q;
                    response_address_q   <= address_q;
                    response_read_data_q <= read_data_q;
                    if (accept_request) begin
                        kind_q      <= request_kind;
                        address_q   <= request_address;
                        phase_q     <= upd7220_pkg::MEM_PHASE_C1;
                        ale_epoch_q <= ~ale_epoch_q;
                    end else begin
                        phase_q <= upd7220_pkg::MEM_PHASE_IDLE;
                    end
                end
                default:
                    phase_q <= upd7220_pkg::MEM_PHASE_IDLE;
            endcase
        end
    end

    // The memory supplies display data through the end of D2 and RMW read data
    // through the falling edge in the middle of C3.
    always_ff @(negedge clk_2x or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            read_data_q       <= 16'h0000;
            ale_fall_epoch_q  <= 1'b0;
            dbin_n_q          <= 1'b1;
        end else if (reset_command) begin
            read_data_q       <= 16'h0000;
            ale_fall_epoch_q  <= ale_epoch_q;
            dbin_n_q          <= 1'b1;
        end else begin
            if (phase_q == upd7220_pkg::MEM_PHASE_C1) begin
                ale_fall_epoch_q <= ale_epoch_q;
            end
            if ((kind_q == upd7220_pkg::MEM_CYCLE_DISPLAY)
                && (phase_q == upd7220_pkg::MEM_PHASE_C2)) begin
                read_data_q <= mem_ad_i;
            end else if ((kind_q == upd7220_pkg::MEM_CYCLE_RMW)
                         && (phase_q == upd7220_pkg::MEM_PHASE_C3)) begin
                read_data_q <= mem_ad_i;
            end

            if ((kind_q == upd7220_pkg::MEM_CYCLE_RMW)
                && (phase_q == upd7220_pkg::MEM_PHASE_C2)) begin
                dbin_n_q <= 1'b0;
            end else begin
                dbin_n_q <= 1'b1;
            end
        end
    end

`ifndef SYNTHESIS
    property p_request_kind_valid;
        @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
            accept_request |->
                (request_kind inside {upd7220_pkg::MEM_CYCLE_DISPLAY,
                                      upd7220_pkg::MEM_CYCLE_RMW});
    endproperty
    property p_ad_direction;
        @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
            mem_ad_oe |->
                ((phase_q == upd7220_pkg::MEM_PHASE_C1)
                 || ((kind_q == upd7220_pkg::MEM_CYCLE_RMW)
                     && (phase_q == upd7220_pkg::MEM_PHASE_C4)));
    endproperty
    property p_dbin_never_contends;
        @(negedge clk_2x) disable iff (!integration_reset_n || reset_command)
            !mem_dbin_n |-> !mem_ad_oe;
    endproperty
    property p_rmw_read_before_write;
        @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
            ((kind_q == upd7220_pkg::MEM_CYCLE_RMW)
             && (phase_q == upd7220_pkg::MEM_PHASE_C4))
            |-> mem_dbin_n;
    endproperty
    property p_rmw_write_data_stable;
        @(negedge clk_2x) disable iff (!integration_reset_n || reset_command)
            ((kind_q == upd7220_pkg::MEM_CYCLE_RMW)
             && (phase_q == upd7220_pkg::MEM_PHASE_C4))
            |-> (mem_ad_o == write_data_q);
    endproperty

    assert property (p_request_kind_valid)
        else $error("invalid display-memory cycle kind requested");
    assert property (p_ad_direction)
        else $error("AD bus driven outside address or RMW write phase");
    assert property (p_dbin_never_contends)
        else $error("GDC and memory attempted to drive AD simultaneously");
    assert property (p_rmw_read_before_write)
        else $error("RMW write phase began before DBIN returned inactive");
    assert property (p_rmw_write_data_stable)
        else $error("RMW write data changed within cycle four");
`endif

endmodule

`default_nettype wire
