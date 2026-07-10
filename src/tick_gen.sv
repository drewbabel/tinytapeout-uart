module tick_gen #(
    parameter int DIVISOR = 4,
    parameter int Width   = $clog2(DIVISOR)
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic             clr,
    input  logic [Width-1:0] divisor,
    output logic             tick
);

  logic [Width-1:0] limit;
  logic [Width-1:0] cnt;

  assign limit = (divisor == '0) ? $bits(limit)'(DIVISOR - 1) : divisor - 1'b1;

  always_ff @(posedge clk) begin
    if (!rst_n) cnt <= '0;
    else if (clr) cnt <= '0;
    else cnt <= (cnt == limit) ? '0 : cnt + 1'b1;
  end

  assign tick = (cnt == limit);

endmodule
