`default_nettype none

module upd7220_pram (
    input  logic                       clk_2x,
    input  logic                       integration_reset_n,
    input  logic                       reset_command,

    input  logic                       parameter_valid,
    input  upd7220_pkg::command_kind_t parameter_kind,
    input  logic [3:0]                 start_address,
    input  logic [3:0]                 parameter_index,
    input  logic [7:0]                 parameter_data,

    output logic [127:0]               parameter_ram,
    output logic [15:0]                programmed_mask
);

    logic [127:0] parameter_ram_q;
    logic [15:0]  programmed_mask_q;
    logic [4:0]   write_address;

    assign parameter_ram = parameter_ram_q;
    assign programmed_mask = programmed_mask_q;
    assign write_address = {1'b0, start_address}
        + {1'b0, parameter_index};

    always_ff @(posedge clk_2x or negedge integration_reset_n) begin
        if (!integration_reset_n) begin
            parameter_ram_q   <= 128'h0;
            programmed_mask_q <= 16'h0000;
        end else if (!reset_command && parameter_valid
                     && (parameter_kind == upd7220_pkg::CMD_PRAM)
                     && (write_address < 5'd16)) begin
            parameter_ram_q[write_address * 8 +: 8] <= parameter_data;
            programmed_mask_q[write_address[3:0]] <= 1'b1;
        end
    end

`ifndef SYNTHESIS
    property p_pram_write_address_in_range;
        @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
            (parameter_valid && (parameter_kind == upd7220_pkg::CMD_PRAM))
            |-> (write_address < 5'd16);
    endproperty
    assert property (p_pram_write_address_in_range)
        else $error("PRAM parameter address exceeded RA15");

    generate
        for (genvar byte_index = 0; byte_index < 16; byte_index++) begin : g_byte_write
            property p_selected_byte_is_loaded;
                @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
                    (parameter_valid
                     && (parameter_kind == upd7220_pkg::CMD_PRAM)
                     && (write_address == byte_index))
                    |=> ((parameter_ram_q[byte_index * 8 +: 8]
                           == $past(parameter_data))
                         && programmed_mask_q[byte_index]);
            endproperty
            property p_unselected_byte_is_stable;
                @(posedge clk_2x) disable iff (!integration_reset_n || reset_command)
                    (parameter_valid
                     && (parameter_kind == upd7220_pkg::CMD_PRAM)
                     && (write_address != byte_index))
                    |=> $stable(parameter_ram_q[byte_index * 8 +: 8]);
            endproperty

            assert property (p_selected_byte_is_loaded)
                else $error("PRAM write did not load the selected byte");
            assert property (p_unselected_byte_is_stable)
                else $error("PRAM write modified an unselected byte");
        end
    endgenerate

    property p_functional_reset_retains_pram;
        @(posedge clk_2x) disable iff (!integration_reset_n)
            reset_command |=>
                ($stable(parameter_ram_q) && $stable(programmed_mask_q));
    endproperty

    assert property (p_functional_reset_retains_pram)
        else $error("functional RESET changed retained Parameter RAM state");
`endif

endmodule

`default_nettype wire
