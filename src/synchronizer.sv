module synchronizer #(
    parameter int WIDTH = 1
) (
    input logic clk,
    input logic rst_n,
    input logic [WIDTH-1:0] d,
    output logic [WIDTH-1:0] q
);

  logic [WIDTH-1:0] ff;

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      ff <= '0;
      q  <= '0;
    end else begin
      ff <= d;
      q  <= ff;
    end
  end

endmodule
