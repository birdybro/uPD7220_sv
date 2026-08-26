`default_nettype none

module upd7220_vertical_timing (
    input  logic                          clk_2x,
    input  logic                          integration_reset_n,
    input  logic                          reset_command,
    input  logic                          line_advance_ce,

    input  logic [5:0]                    vsync_width,
    input  logic [6:0]                    vertical_front_porch,
    input  logic [10:0]                   active_lines,
    input  logic [6:0]                    vertical_back_porch,

    output logic                          vsync,
    output logic                          vertical_blank,
    output logic                          active_line,
    output logic                          field_start,
    output upd7220_pkg::vertical_phase_t vertical_phase,
    output logic [10:0]                   vertical_line_index
);

    upd7220_pkg::vertical_phase_t vertical_phase_q;
    logic [10:0] vertical_line_index_q;
    logic [10:0] current_phase_length;
    logic        field_start_q;

    always_comb begin
        case (vertical_phase_q)
            upd7220_pkg::VPHASE_FRONT_PORCH:
                current_phase_length = {4'b0000, vertical_front_porch};
            upd7220_pkg::VPHASE_SYNC:
                current_phase_length = {5'b00000, vsync_width};
            upd7220_pkg::VPHASE_BACK_PORCH:
                current_phase_length = {4'b0000, vertical_back_porch};
            upd7220_pkg::VPHASE_ACTIVE:
                current_phase_length = active_lines;
            default:
                current_phase_length = 11'd1;
        endcase
    end

    assign vertical_phase = vertical_phase_q;
    assign vertical_line_index = vertical_line_index_q;
    assign vsync = vertical_phase_q == upd7220_pkg::VPHASE_SYNC;
    assign vertical_blank = vertical_phase_q != upd7220_pkg::VPHASE_ACTIVE;
    assign active_line = vertical_phase_q == upd7220_pkg::VPHASE_ACTIVE;
    assign field_start = field_start_q;

    // A normal/noninterlaced vertical transition coincides with the leading
    // BLANK edge at the active-word-to-HFP boundary. line_advance_ce is
    // combinational from the horizontal state and is stable before this edge.
    always_ff @(negedge clk_2x or negedge integration_reset_n) begin : p_vertical
        if (!integration_reset_n) begin
            vertical_phase_q      <= upd7220_pkg::VPHASE_FRONT_PORCH;
            vertical_line_index_q <= 11'd0;
            field_start_q         <= 1'b0;
        end else if (reset_command) begin
            vertical_phase_q      <= upd7220_pkg::VPHASE_FRONT_PORCH;
            vertical_line_index_q <= 11'd0;
            field_start_q         <= 1'b0;
        end else begin
            field_start_q <= 1'b0;
            if (line_advance_ce) begin
                if (vertical_line_index_q >= (current_phase_length - 11'd1)) begin
                    vertical_line_index_q <= 11'd0;
                    case (vertical_phase_q)
                        upd7220_pkg::VPHASE_FRONT_PORCH:
                            vertical_phase_q <= upd7220_pkg::VPHASE_SYNC;
                        upd7220_pkg::VPHASE_SYNC:
                            vertical_phase_q <= upd7220_pkg::VPHASE_BACK_PORCH;
                        upd7220_pkg::VPHASE_BACK_PORCH:
                            vertical_phase_q <= upd7220_pkg::VPHASE_ACTIVE;
                        upd7220_pkg::VPHASE_ACTIVE: begin
                            vertical_phase_q <= upd7220_pkg::VPHASE_FRONT_PORCH;
                            field_start_q    <= 1'b1;
                        end
                        default:
                            vertical_phase_q <= upd7220_pkg::VPHASE_FRONT_PORCH;
                    endcase
                end else begin
                    vertical_line_index_q <= vertical_line_index_q + 11'd1;
                end
            end
        end
    end

`ifndef SYNTHESIS
    property p_nonzero_vertical_intervals;
        @(negedge clk_2x) disable iff (!integration_reset_n || reset_command)
            (vsync_width != 6'd0)
            && (vertical_front_porch != 7'd0)
            && (active_lines != 11'd0)
            && (vertical_back_porch != 7'd0);
    endproperty

    assert property (p_nonzero_vertical_intervals)
        else $error("vertical timing interval cannot be zero");
`endif

endmodule

`default_nettype wire
