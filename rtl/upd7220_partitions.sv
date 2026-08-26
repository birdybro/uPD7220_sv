`default_nettype none

module upd7220_partitions (
    input  logic                        clk_2x,
    input  logic                        integration_reset_n,
    input  logic                        reset_command,

    input  upd7220_pkg::display_mode_t  display_mode,
    input  logic [8:0]                  pitch,
    input  logic [5:0]                  lines_per_character_row,
    input  logic [127:0]                parameter_ram,

    input  logic                        active_line,
    input  logic                        line_start,
    input  logic                        display_advance,

    output logic                        partition_active,
    output logic [1:0]                  partition_index,
    output logic [10:0]                 partition_line_index,
    output logic [10:0]                 partition_line_count,
    output logic [5:0]                  character_scanline,
    output logic [17:0]                 partition_start_address,
    output logic [17:0]                 dad,
    output logic                        image_area,
    output logic                        graphics_area,
    output logic                        wide_access
);

    logic [7:0] pram_byte [0:15];
    logic [17:0] decoded_start [0:3];
    logic [10:0] decoded_length [0:3];
    logic [3:0] decoded_image;
    logic [3:0] decoded_wide;

    logic active_line_q;
    logic partition_active_q;
    logic [1:0] partition_index_q;
    logic [2:0] partition_count_q;
    logic [10:0] partition_line_index_q;
    logic [10:0] partition_line_count_q;
    logic [5:0] character_scanline_q;
    logic [17:0] partition_start_address_q;
    logic [17:0] line_base_q;
    logic [17:0] dad_q;
    logic image_area_q;
    logic graphics_area_q;
    logic wide_access_q;
    logic display_repeat_q;
    upd7220_pkg::display_mode_t address_mode_q;

    logic [1:0] next_partition_index;
    logic [2:0] decoded_partition_count;
    logic [5:0] effective_lines_per_row;

    function automatic logic [17:0] normalize_address(
        logic [17:0] raw_address,
        upd7220_pkg::display_mode_t mode
    );
        logic [17:0] result;
        unique case (mode)
            upd7220_pkg::DISPLAY_CHARACTER:
                result = {5'b00000, raw_address[12:0]};
            upd7220_pkg::DISPLAY_MIXED:
                result = {2'b00, raw_address[15:0]};
            upd7220_pkg::DISPLAY_GRAPHICS:
                result = raw_address[17:0];
            default:
                result = 18'h00000;
        endcase
        return result;
    endfunction

    function automatic logic [17:0] advance_address(
        logic [17:0] address,
        logic [9:0] amount,
        upd7220_pkg::display_mode_t mode
    );
        logic [17:0] wrapped_address;
        wrapped_address = address + {{8{1'b0}}, amount};
        return normalize_address(wrapped_address, mode);
    endfunction

    generate
        for (genvar byte_index = 0; byte_index < 16; byte_index++) begin : g_bytes
            assign pram_byte[byte_index] =
                parameter_ram[byte_index * 8 +: 8];
        end
    endgenerate

    always_comb begin : p_decode
        logic [9:0] raw_length;
        for (integer area = 0; area < 4; area = area + 1) begin
            if (display_mode == upd7220_pkg::DISPLAY_CHARACTER) begin
                decoded_start[area] = {
                    5'b00000,
                    pram_byte[area * 4 + 1][4:0],
                    pram_byte[area * 4]
                };
            end else begin
                decoded_start[area] = {
                    pram_byte[area * 4 + 2][1:0],
                    pram_byte[area * 4 + 1],
                    pram_byte[area * 4]
                };
            end
            raw_length = {
                pram_byte[area * 4 + 3][5:0],
                pram_byte[area * 4 + 2][7:4]
            };
            decoded_length[area] = (raw_length == 10'd0)
                ? 11'd1024 : {1'b0, raw_length};
            decoded_image[area] = pram_byte[area * 4 + 3][6];
            decoded_wide[area] = pram_byte[area * 4 + 3][7];
        end
    end

    always_comb begin
        unique case (display_mode)
            upd7220_pkg::DISPLAY_CHARACTER:
                decoded_partition_count = 3'd4;
            upd7220_pkg::DISPLAY_GRAPHICS,
            upd7220_pkg::DISPLAY_MIXED:
                decoded_partition_count = 3'd2;
            default:
                decoded_partition_count = 3'd0;
        endcase
        effective_lines_per_row = (lines_per_character_row == 6'd0)
            ? 6'd1 : lines_per_character_row;
        if ({1'b0, partition_index_q} + 3'd1 >= partition_count_q) begin
            next_partition_index = 2'd0;
        end else begin
            next_partition_index = partition_index_q + 2'd1;
        end
    end

    // Keep the descriptor state across horizontal and vertical blanking, but
    // only advertise an active display partition during an active scan line.
    assign partition_active = partition_active_q && active_line;
    assign partition_index = partition_index_q;
    assign partition_line_index = partition_line_index_q;
    assign partition_line_count = partition_line_count_q;
    assign character_scanline = character_scanline_q;
    assign partition_start_address = partition_start_address_q;
    assign dad = dad_q;
    assign image_area = image_area_q;
    assign graphics_area = graphics_area_q;
    assign wide_access = wide_access_q;

    always_ff @(posedge clk_2x or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            active_line_q              <= 1'b0;
            partition_active_q         <= 1'b0;
            partition_index_q          <= 2'd0;
            partition_count_q          <= 3'd0;
            partition_line_index_q     <= 11'd0;
            partition_line_count_q     <= 11'd1;
            character_scanline_q       <= 6'd0;
            partition_start_address_q  <= 18'h00000;
            line_base_q                <= 18'h00000;
            dad_q                      <= 18'h00000;
            image_area_q               <= 1'b0;
            graphics_area_q            <= 1'b0;
            wide_access_q              <= 1'b0;
            display_repeat_q           <= 1'b0;
            address_mode_q             <= upd7220_pkg::DISPLAY_INVALID;
        end else if (reset_command) begin
            active_line_q              <= 1'b0;
            partition_active_q         <= 1'b0;
            partition_index_q          <= 2'd0;
            partition_count_q          <= 3'd0;
            partition_line_index_q     <= 11'd0;
            partition_line_count_q     <= 11'd1;
            character_scanline_q       <= 6'd0;
            partition_start_address_q  <= 18'h00000;
            line_base_q                <= 18'h00000;
            dad_q                      <= 18'h00000;
            image_area_q               <= 1'b0;
            graphics_area_q            <= 1'b0;
            wide_access_q              <= 1'b0;
            display_repeat_q           <= 1'b0;
            address_mode_q             <= upd7220_pkg::DISPLAY_INVALID;
        end else begin
            active_line_q <= active_line;

            // The transition into the active vertical interval fetches the
            // first four-byte descriptor, as described for VBP updates.
            if (active_line && !active_line_q) begin
                partition_active_q        <= decoded_partition_count != 3'd0;
                partition_index_q         <= 2'd0;
                partition_count_q         <= decoded_partition_count;
                partition_line_index_q    <= 11'd0;
                partition_line_count_q    <= decoded_length[0];
                character_scanline_q      <= 6'd0;
                partition_start_address_q <= normalize_address(
                    decoded_start[0], display_mode
                );
                line_base_q <= normalize_address(
                    decoded_start[0], display_mode
                );
                dad_q <= normalize_address(
                    decoded_start[0], display_mode
                );
                image_area_q    <= decoded_image[0];
                graphics_area_q <=
                    (display_mode == upd7220_pkg::DISPLAY_GRAPHICS)
                    || ((display_mode == upd7220_pkg::DISPLAY_MIXED)
                        && decoded_image[0]);
                wide_access_q    <= decoded_wide[0];
                display_repeat_q <= 1'b0;
                address_mode_q   <= display_mode;
            end else if (active_line && line_start && partition_active_q) begin
                display_repeat_q <= 1'b0;
                if (partition_line_index_q + 11'd1
                    >= partition_line_count_q) begin
                    partition_index_q      <= next_partition_index;
                    partition_count_q      <= decoded_partition_count;
                    partition_line_index_q <= 11'd0;
                    partition_line_count_q <=
                        decoded_length[next_partition_index];
                    character_scanline_q <= 6'd0;
                    partition_start_address_q <= normalize_address(
                        decoded_start[next_partition_index], display_mode
                    );
                    line_base_q <= normalize_address(
                        decoded_start[next_partition_index], display_mode
                    );
                    dad_q <= normalize_address(
                        decoded_start[next_partition_index], display_mode
                    );
                    image_area_q <= decoded_image[next_partition_index];
                    graphics_area_q <=
                        (display_mode == upd7220_pkg::DISPLAY_GRAPHICS)
                        || ((display_mode == upd7220_pkg::DISPLAY_MIXED)
                            && decoded_image[next_partition_index]);
                    wide_access_q <= decoded_wide[next_partition_index];
                    address_mode_q <= display_mode;
                end else begin
                    partition_line_index_q <=
                        partition_line_index_q + 11'd1;
                    if (graphics_area_q) begin
                        line_base_q <= advance_address(
                            line_base_q, {1'b0, pitch}, address_mode_q
                        );
                        dad_q <= advance_address(
                            line_base_q, {1'b0, pitch}, address_mode_q
                        );
                        character_scanline_q <= 6'd0;
                    end else if (character_scanline_q + 6'd1
                                 >= effective_lines_per_row) begin
                        line_base_q <= advance_address(
                            line_base_q, {1'b0, pitch}, address_mode_q
                        );
                        dad_q <= advance_address(
                            line_base_q, {1'b0, pitch}, address_mode_q
                        );
                        character_scanline_q <= 6'd0;
                    end else begin
                        dad_q <= line_base_q;
                        character_scanline_q <= character_scanline_q + 6'd1;
                    end
                end
            end else if (active_line && display_advance
                         && partition_active_q) begin
                if (image_area_q && !display_repeat_q) begin
                    display_repeat_q <= 1'b1;
                end else begin
                    display_repeat_q <= 1'b0;
                    dad_q <= advance_address(
                        dad_q,
                        wide_access_q ? 10'd2 : 10'd1,
                        address_mode_q
                    );
                end
            end

            if (!active_line) begin
                display_repeat_q <= 1'b0;
            end
        end
    end

`ifndef SYNTHESIS
    property p_partition_index_in_range;
        @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
            partition_active_q |->
                ({1'b0, partition_index_q} < partition_count_q);
    endproperty
    property p_partition_line_in_range;
        @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
            partition_active_q |->
                (partition_line_index_q < partition_line_count_q);
    endproperty
    property p_mode_specific_address_width;
        @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
            partition_active_q |->
                (((address_mode_q == upd7220_pkg::DISPLAY_CHARACTER)
                  && (dad_q[17:13] == 5'b00000))
                 || ((address_mode_q == upd7220_pkg::DISPLAY_MIXED)
                     && (dad_q[17:16] == 2'b00))
                 || (address_mode_q == upd7220_pkg::DISPLAY_GRAPHICS));
    endproperty

    assert property (p_partition_index_in_range)
        else $error("display partition index exceeded the mode's area count");
    assert property (p_partition_line_in_range)
        else $error("display partition line counter exceeded its descriptor");
    assert property (p_mode_specific_address_width)
        else $error("DAD exceeded the selected display mode address width");
`endif

endmodule

`default_nettype wire
