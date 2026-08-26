`default_nettype none

module upd7220_pitch #(
    parameter upd7220_pkg::gdc_variant_t GDC_VARIANT = upd7220_pkg::GDC_7220
) (
    input  logic                       clk_2x,
    input  logic                       integration_reset_n,
    input  logic                       parameter_valid,
    input  upd7220_pkg::command_kind_t parameter_kind,
    input  logic [3:0]                 parameter_index,
    input  logic [7:0]                 parameter_data,
    output logic [8:0]                 pitch
);

    logic [7:0] pitch_q;

    // The base 7220/82720 pitch register is eight bits. P2 of RESET/SYNC
    // loads AW=P2+2 into that register, so the valid AW=256 case wraps to
    // 00h. The 7220A PH extension is intentionally deferred to its profile.
    assign pitch = {1'b0, pitch_q};

    always_ff @(posedge clk_2x or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            pitch_q <= 8'h00;
        end else if (parameter_valid) begin
            if (((parameter_kind == upd7220_pkg::CMD_RESET)
                 || (parameter_kind == upd7220_pkg::CMD_SYNC))
                && (parameter_index == 4'd1)) begin
                pitch_q <= parameter_data + 8'd2;
            end else if ((parameter_kind == upd7220_pkg::CMD_PITCH)
                         && (parameter_index == 4'd0)) begin
                pitch_q <= parameter_data;
            end
        end
    end

    generate
        if (!upd7220_pkg::valid_variant(GDC_VARIANT)) begin : g_invalid_variant
            initial $error("GDC_VARIANT is not a supported uPD7220 family profile");
        end
    endgenerate

`ifndef SYNTHESIS
    property p_pitch_parameter_index;
        @(posedge clk_2x) disable iff (!integration_reset_n)
            (parameter_valid && (parameter_kind == upd7220_pkg::CMD_PITCH))
            |-> (parameter_index == 4'd0);
    endproperty

    assert property (p_pitch_parameter_index)
        else $error("PITCH parameter index must be zero");
`endif

endmodule

`default_nettype wire
