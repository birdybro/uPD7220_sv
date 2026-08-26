`default_nettype none

package upd7220_pkg;

    typedef enum logic [1:0] {
        GDC_7220  = 2'd0,
        GDC_82720 = 2'd1,
        GDC_7220A = 2'd2
    } gdc_variant_t;

    typedef enum logic [4:0] {
        CMD_INVALID = 5'd0,
        CMD_RESET   = 5'd1,
        CMD_SYNC    = 5'd2,
        CMD_VSYNC   = 5'd3,
        CMD_CCHAR   = 5'd4,
        CMD_START   = 5'd5,
        CMD_BCTRL   = 5'd6,
        CMD_ZOOM    = 5'd7,
        CMD_CURS    = 5'd8,
        CMD_PRAM    = 5'd9,
        CMD_PITCH   = 5'd10,
        CMD_WDAT    = 5'd11,
        CMD_MASK    = 5'd12,
        CMD_FIGS    = 5'd13,
        CMD_FIGD    = 5'd14,
        CMD_GCHRD   = 5'd15,
        CMD_RDAT    = 5'd16,
        CMD_CURD    = 5'd17,
        CMD_LPRD    = 5'd18,
        CMD_DMAR    = 5'd19,
        CMD_DMAW    = 5'd20
    } command_kind_t;

    typedef enum logic [1:0] {
        DISPLAY_MIXED     = 2'b00,
        DISPLAY_GRAPHICS  = 2'b01,
        DISPLAY_CHARACTER = 2'b10,
        DISPLAY_INVALID   = 2'b11
    } display_mode_t;

    typedef enum logic [1:0] {
        FRAME_NONINTERLACED = 2'b00,
        FRAME_INVALID       = 2'b01,
        FRAME_REPEAT_FIELD  = 2'b10,
        FRAME_INTERLACED    = 2'b11
    } framing_mode_t;

    localparam int unsigned HOST_DATA_WIDTH = 8;
    localparam int unsigned MEM_DATA_WIDTH = 16;
    localparam int unsigned FIFO_DEPTH = 16;

    function automatic logic valid_variant(gdc_variant_t variant);
        return variant inside {GDC_7220, GDC_82720, GDC_7220A};
    endfunction

    function automatic logic valid_transfer_type(logic [1:0] transfer_type);
        // Figure 12 encodes TYPE=01 as invalid. The other three values select
        // word, low-byte, and high-byte transfers respectively.
        return transfer_type != 2'b01;
    endfunction

    function automatic command_kind_t decode_command(logic [7:0] opcode);
        command_kind_t result;
        result = CMD_INVALID;
        casez (opcode)
            8'h00:       result = CMD_RESET;
            8'b0000_111?: result = CMD_SYNC;
            8'b0110_111?: result = CMD_VSYNC;
            8'h4b:       result = CMD_CCHAR;
            8'h6b:       result = CMD_START;
            8'b0000_110?: result = CMD_BCTRL;
            8'h46:       result = CMD_ZOOM;
            8'h49:       result = CMD_CURS;
            8'b0111_????: result = CMD_PRAM;
            8'h47:       result = CMD_PITCH;
            8'b001?_?0??: begin
                if (valid_transfer_type(opcode[4:3])) begin
                    result = CMD_WDAT;
                end
            end
            8'h4a:       result = CMD_MASK;
            8'h4c:       result = CMD_FIGS;
            8'h6c:       result = CMD_FIGD;
            8'h68:       result = CMD_GCHRD;
            8'b101?_?0??: begin
                if (valid_transfer_type(opcode[4:3])) begin
                    result = CMD_RDAT;
                end
            end
            8'hE0:       result = CMD_CURD;
            8'hC0:       result = CMD_LPRD;
            8'b101?_?1??: begin
                if (valid_transfer_type(opcode[4:3])) begin
                    result = CMD_DMAR;
                end
            end
            8'b001?_?1??: begin
                if (valid_transfer_type(opcode[4:3])) begin
                    result = CMD_DMAW;
                end
            end
            default:     result = CMD_INVALID;
        endcase
        return result;
    endfunction

    function automatic logic [4:0] command_parameter_limit(
        command_kind_t kind,
        logic [4:0] opcode_fields
    );
        logic [4:0] result;
        result = 5'd0;
        case (kind)
            CMD_RESET,
            CMD_SYNC:  result = 5'd8;
            CMD_CCHAR: result = 5'd3;
            CMD_ZOOM,
            CMD_PITCH: result = 5'd1;
            CMD_CURS:  result = 5'd3;
            CMD_PRAM:  result = 5'd16 - {1'b0, opcode_fields[3:0]};
            CMD_WDAT: begin
                result = (opcode_fields[4:3] == 2'b00) ? 5'd2 : 5'd1;
            end
            CMD_MASK:  result = 5'd2;
            CMD_FIGS:  result = 5'd11;
            default:   result = 5'd0;
        endcase
        return result;
    endfunction

    function automatic logic command_repeats_parameter_group(command_kind_t kind);
        return kind == CMD_WDAT;
    endfunction

endpackage

`default_nettype wire
