`default_nettype none

module upd7220_sync_control #(
    parameter upd7220_pkg::gdc_variant_t GDC_VARIANT = upd7220_pkg::GDC_7220
) (
    input  logic                       clk_2x,
    input  logic                       integration_reset_n,
    input  logic                       reset_command,

    input  logic                       command_start,
    input  upd7220_pkg::command_kind_t started_kind,
    input  logic [7:0]                 started_opcode,
    input  logic                       parameter_valid,
    input  upd7220_pkg::command_kind_t parameter_kind,
    input  logic [3:0]                 parameter_index,
    input  logic [7:0]                 parameter_data,

    output logic                       display_enable,
    output logic                       sync_master,
    output logic [7:0]                 programmed_mask,
    output logic [7:0]                 sync_p1,
    output logic [7:0]                 sync_p2,
    output logic [7:0]                 sync_p3,
    output logic [7:0]                 sync_p4,
    output logic [7:0]                 sync_p5,
    output logic [7:0]                 sync_p6,
    output logic [7:0]                 sync_p7,
    output logic [7:0]                 sync_p8,

    output upd7220_pkg::display_mode_t display_mode,
    output upd7220_pkg::framing_mode_t framing_mode,
    output logic                       refresh_enable,
    output logic                       drawing_during_retrace_only,
    output logic [8:0]                 active_words,
    output logic [5:0]                 hsync_width,
    output logic [5:0]                 vsync_width,
    output logic [6:0]                 horizontal_front_porch,
    output logic [6:0]                 horizontal_back_porch,
    output logic [6:0]                 vertical_front_porch,
    output logic [10:0]                active_lines,
    output logic [6:0]                 vertical_back_porch
);

    logic [7:0] sync_parameter_q [0:7];
    logic [7:0] programmed_mask_q;
    logic       display_enable_q;
    logic       sync_master_q;
    logic [4:0] raw_vsync_width;
    logic [9:0] raw_active_lines;

    assign display_enable = display_enable_q;
    assign sync_master = sync_master_q;
    assign programmed_mask = programmed_mask_q;
    assign sync_p1 = sync_parameter_q[0];
    assign sync_p2 = sync_parameter_q[1];
    assign sync_p3 = sync_parameter_q[2];
    assign sync_p4 = sync_parameter_q[3];
    assign sync_p5 = sync_parameter_q[4];
    assign sync_p6 = sync_parameter_q[5];
    assign sync_p7 = sync_parameter_q[6];
    assign sync_p8 = sync_parameter_q[7];

    assign display_mode = upd7220_pkg::display_mode_t'({
        sync_parameter_q[0][5], sync_parameter_q[0][1]
    });
    assign framing_mode = upd7220_pkg::framing_mode_t'({
        sync_parameter_q[0][3], sync_parameter_q[0][0]
    });
    assign refresh_enable = sync_parameter_q[0][2];
    assign drawing_during_retrace_only = sync_parameter_q[0][4];

    assign active_words = {1'b0, sync_parameter_q[1]} + 9'd2;
    assign hsync_width = {1'b0, sync_parameter_q[2][4:0]} + 6'd1;
    assign raw_vsync_width = {
        sync_parameter_q[3][1:0], sync_parameter_q[2][7:5]
    };
    assign vsync_width = (raw_vsync_width == 5'd0)
        ? 6'd32 : {1'b0, raw_vsync_width};
    assign horizontal_front_porch =
        {1'b0, sync_parameter_q[3][7:2]} + 7'd1;
    assign horizontal_back_porch =
        {1'b0, sync_parameter_q[4][5:0]} + 7'd1;
    assign vertical_front_porch = (sync_parameter_q[5][5:0] == 6'd0)
        ? 7'd64 : {1'b0, sync_parameter_q[5][5:0]};
    assign raw_active_lines = {
        sync_parameter_q[7][1:0], sync_parameter_q[6]
    };
    assign active_lines = (raw_active_lines == 10'd0)
        ? 11'd1024 : {1'b0, raw_active_lines};
    assign vertical_back_porch = (sync_parameter_q[7][7:2] == 6'd0)
        ? 7'd64 : {1'b0, sync_parameter_q[7][7:2]};

    always_ff @(posedge clk_2x or negedge integration_reset_n) begin : p_registers
        integer index;
        if (!integration_reset_n) begin
            for (index = 0; index < 8; index = index + 1) begin
                sync_parameter_q[index] <= 8'h00;
            end
            programmed_mask_q <= 8'h00;
            display_enable_q  <= 1'b0;
            sync_master_q     <= 1'b0;
        end else begin
            if (reset_command) begin
                // Base RESET blanks but explicitly retains loaded parameters.
                display_enable_q <= 1'b0;
            end else if (command_start) begin
                case (started_kind)
                    upd7220_pkg::CMD_SYNC,
                    upd7220_pkg::CMD_BCTRL:
                        display_enable_q <= started_opcode[0];
                    upd7220_pkg::CMD_START:
                        display_enable_q <= 1'b1;
                    default: begin
                    end
                endcase
            end

            if (command_start && (started_kind == upd7220_pkg::CMD_VSYNC)) begin
                sync_master_q <= started_opcode == 8'h6f;
            end

            if (parameter_valid
                && ((parameter_kind == upd7220_pkg::CMD_RESET)
                    || (parameter_kind == upd7220_pkg::CMD_SYNC))
                && (parameter_index < 4'd8)) begin
                sync_parameter_q[parameter_index[2:0]] <= parameter_data;
                programmed_mask_q[parameter_index[2:0]] <= 1'b1;
            end
        end
    end

    generate
        if (!upd7220_pkg::valid_variant(GDC_VARIANT)) begin : g_invalid_variant
            initial $error("GDC_VARIANT is not a supported uPD7220 family profile");
        end
    endgenerate

`ifndef SYNTHESIS
    property p_sync_parameter_index;
        @(posedge clk_2x) disable iff (!integration_reset_n)
            (parameter_valid
             && ((parameter_kind == upd7220_pkg::CMD_RESET)
                 || (parameter_kind == upd7220_pkg::CMD_SYNC)))
            |-> (parameter_index < 4'd8);
    endproperty

    assert property (p_sync_parameter_index)
        else $error("RESET/SYNC parameter index exceeded P8");
`endif

endmodule

`default_nettype wire
