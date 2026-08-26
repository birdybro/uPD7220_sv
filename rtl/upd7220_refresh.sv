`default_nettype none

// The enabled refresh sequencer claims every two-clock display-cycle slot
// during HSYNC. NEC and Intel specify only AD0-AD7 as the refresh row address;
// the remaining address outputs are held low as a deterministic FPGA-facing
// convention and are not claimed as original-silicon behavior.
module upd7220_refresh (
    input  logic        clk_2x,
    input  logic        integration_reset_n,
    input  logic        reset_command,
    input  logic        refresh_enable,
    input  logic        hsync,
    input  logic        request_ready,

    output logic        request_valid,
    output logic        request_accept,
    output logic [17:0] request_address,
    output logic [7:0]  refresh_counter
);

    logic [7:0] refresh_counter_q;

    assign request_valid = refresh_enable && hsync;
    assign request_accept = request_valid && request_ready;
    assign request_address = {10'b0, refresh_counter_q};
    assign refresh_counter = refresh_counter_q;

    always_ff @(posedge clk_2x or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            refresh_counter_q <= 8'h00;
        end else if (reset_command) begin
            refresh_counter_q <= 8'h00;
        end else if (request_accept) begin
            refresh_counter_q <= refresh_counter_q + 8'h01;
        end
    end

`ifndef SYNTHESIS
    property p_only_accept_in_hsync;
        @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
            request_accept |-> (refresh_enable && hsync && request_ready);
    endproperty
    property p_successive_address;
        @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
            request_accept |=>
                (refresh_counter == ($past(refresh_counter) + 8'h01));
    endproperty

    assert property (p_only_accept_in_hsync)
        else $error("refresh cycle accepted outside enabled HSYNC");
    assert property (p_successive_address)
        else $error("refresh counter did not advance after an accepted cycle");
`endif

endmodule

`default_nettype wire
