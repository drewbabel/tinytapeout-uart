module parity #(
    parameter int DATA_BITS = 8
) (
    input  logic [DATA_BITS-1:0] data,
    input  logic                 odd,
    output logic                 p
);

  assign p = odd ? ~(^data) : (^data);

endmodule
