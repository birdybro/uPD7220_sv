`default_nettype none

module upd7220_video_timing (
    input  logic                            clk_2x,
    input  logic                            integration_reset_n,
    input  logic                            reset_command,
    input  logic                            word_time_ce,

    input  logic                            display_enable,
    input  logic [8:0]                      active_words,
    input  logic [5:0]                      hsync_width,
    input  logic [6:0]                      horizontal_front_porch,
    input  logic [6:0]                      horizontal_back_porch,

    output logic                            hsync,
    output logic                            horizontal_blank,
    output logic                            blank,
    output logic                            active_word,
    output logic                            line_start,
    output upd7220_pkg::horizontal_phase_t horizontal_phase,
    output logic [8:0]                      horizontal_word_index
);

    upd7220_pkg::horizontal_phase_t horizontal_phase_q;
    logic [8:0] horizontal_word_index_q;
    logic [8:0] current_phase_length;
    logic       display_enable_q;
    logic       line_start_q;

    always_comb begin
        case (horizontal_phase_q)
            upd7220_pkg::HPHASE_FRONT_PORCH:
                current_phase_length = {2'b00, horizontal_front_porch};
            upd7220_pkg::HPHASE_SYNC:
                current_phase_length = {3'b000, hsync_width};
            upd7220_pkg::HPHASE_BACK_PORCH:
                current_phase_length = {2'b00, horizontal_back_porch};
            upd7220_pkg::HPHASE_ACTIVE:
                current_phase_length = active_words;
            default:
                current_phase_length = 9'd1;
        endcase
    end

    assign horizontal_phase = horizontal_phase_q;
    assign horizontal_word_index = horizontal_word_index_q;
    assign hsync = horizontal_phase_q == upd7220_pkg::HPHASE_SYNC;
    assign horizontal_blank = horizontal_phase_q != upd7220_pkg::HPHASE_ACTIVE;
    assign active_word = horizontal_phase_q == upd7220_pkg::HPHASE_ACTIVE;
    assign blank = !display_enable_q || horizontal_blank;
    assign line_start = line_start_q;

    // Intel 82720 data-sheet page 31 specifies TCO from the falling edge of
    // 2xWCLK to HSYNC/BLANK and the other video outputs. The word-time enable
    // is prepared on the preceding rising edge and is therefore stable here.
    always_ff @(negedge clk_2x or negedge integration_reset_n) begin : p_horizontal
        if (!integration_reset_n) begin
            horizontal_phase_q      <= upd7220_pkg::HPHASE_FRONT_PORCH;
            horizontal_word_index_q <= 9'd0;
            display_enable_q        <= 1'b0;
            line_start_q            <= 1'b0;
        end else if (reset_command) begin
            horizontal_phase_q      <= upd7220_pkg::HPHASE_FRONT_PORCH;
            horizontal_word_index_q <= 9'd0;
            display_enable_q        <= 1'b0;
            line_start_q            <= 1'b0;
        end else begin
            display_enable_q <= display_enable;
            line_start_q     <= 1'b0;

            if (word_time_ce) begin
                if (horizontal_word_index_q >= (current_phase_length - 9'd1)) begin
                    horizontal_word_index_q <= 9'd0;
                    case (horizontal_phase_q)
                        upd7220_pkg::HPHASE_FRONT_PORCH:
                            horizontal_phase_q <= upd7220_pkg::HPHASE_SYNC;
                        upd7220_pkg::HPHASE_SYNC:
                            horizontal_phase_q <= upd7220_pkg::HPHASE_BACK_PORCH;
                        upd7220_pkg::HPHASE_BACK_PORCH:
                            horizontal_phase_q <= upd7220_pkg::HPHASE_ACTIVE;
                        upd7220_pkg::HPHASE_ACTIVE: begin
                            horizontal_phase_q <= upd7220_pkg::HPHASE_FRONT_PORCH;
                            line_start_q       <= 1'b1;
                        end
                        default:
                            horizontal_phase_q <= upd7220_pkg::HPHASE_FRONT_PORCH;
                    endcase
                end else begin
                    horizontal_word_index_q <= horizontal_word_index_q + 9'd1;
                end
            end
        end
    end

`ifndef SYNTHESIS
    property p_nonzero_horizontal_intervals;
        @(negedge clk_2x) disable iff (!integration_reset_n || reset_command)
            (active_words != 9'd0)
            && (hsync_width != 6'd0)
            && (horizontal_front_porch != 7'd0)
            && (horizontal_back_porch != 7'd0);
    endproperty

    assert property (p_nonzero_horizontal_intervals)
        else $error("horizontal timing interval cannot be zero");

`endif

endmodule

`default_nettype wire
