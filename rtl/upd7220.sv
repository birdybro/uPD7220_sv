`default_nettype none

// Pin-faithful functional wrapper. VCC/GND are omitted from the HDL interface,
// and the physical IC has no reset pin: software initialization begins with the
// RESET command. Use upd7220_core directly when an FPGA integration reset is
// required.
module upd7220 #(
    parameter upd7220_pkg::gdc_variant_t GDC_VARIANT = upd7220_pkg::GDC_7220
) (
    input  logic        clk_2x,
    output logic        dbin_n,
    output logic        hsync,
    inout  wire         v_ext_sync,
    output logic        blank,
    output logic        ale,
    output logic        drq,
    input  logic        dack_n,
    input  logic        rd_n,
    input  logic        wr_n,
    input  logic        a0,
    inout  wire [7:0]   db,
    input  logic        lpen,
    inout  wire [15:0]  ad,
    output logic        a16,
    output logic        a17
);

    logic [upd7220_pkg::HOST_DATA_WIDTH-1:0] host_db_i;
    logic [upd7220_pkg::HOST_DATA_WIDTH-1:0] host_db_o;
    logic        host_db_oe;
    logic        v_ext_sync_i;
    logic        v_ext_sync_o;
    logic        v_ext_sync_oe;
    logic [upd7220_pkg::MEM_DATA_WIDTH-1:0] mem_ad_i;
    logic [upd7220_pkg::MEM_DATA_WIDTH-1:0] mem_ad_o;
    logic        mem_ad_oe;
    logic        unused_word_time_ce;

    assign host_db_i = db;
    assign db = host_db_oe ? host_db_o : 8'hzz;
    assign v_ext_sync_i = v_ext_sync;
    assign v_ext_sync = v_ext_sync_oe ? v_ext_sync_o : 1'bz;
    assign mem_ad_i = ad;
    assign ad = mem_ad_oe ? mem_ad_o : 16'hzzzz;

    upd7220_core #(
        .GDC_VARIANT(GDC_VARIANT)
    ) core (
        .clk_2x,
        .integration_reset_n (1'b1),
        .host_rd_n            (rd_n),
        .host_wr_n            (wr_n),
        .host_a0              (a0),
        .host_db_i,
        .host_db_o,
        .host_db_oe,
        .mem_dbin_n           (dbin_n),
        .hsync,
        .v_ext_sync_i,
        .v_ext_sync_o,
        .v_ext_sync_oe,
        .blank,
        .mem_ale              (ale),
        .drq,
        .dack_n,
        .mem_ad_i,
        .mem_ad_o,
        .mem_ad_oe,
        .mem_a16              (a16),
        .mem_a17              (a17),
        .lpen,
        .word_time_ce         (unused_word_time_ce)
    );

endmodule

`default_nettype wire
