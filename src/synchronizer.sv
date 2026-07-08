module synchronizer (
    input  logic clk,
    input  logic d,
    output logic q
);

  logic ff;

  always_ff @(posedge clk) begin
    ff <= d;
    q  <= ff;
  end

endmodule
