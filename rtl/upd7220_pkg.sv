`default_nettype none

package upd7220_pkg;

    typedef enum logic [1:0] {
        GDC_7220  = 2'd0,
        GDC_82720 = 2'd1,
        GDC_7220A = 2'd2
    } gdc_variant_t;

    localparam int unsigned HOST_DATA_WIDTH = 8;
    localparam int unsigned MEM_DATA_WIDTH = 16;

    function automatic logic valid_variant(gdc_variant_t variant);
        return variant inside {GDC_7220, GDC_82720, GDC_7220A};
    endfunction

endpackage

`default_nettype wire
