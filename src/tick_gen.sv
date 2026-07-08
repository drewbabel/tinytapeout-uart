module tick_gen #(
    parameter int DIVISOR = 4
) (
    input  logic clk,
    input  logic rst_n,
    input  logic clr,
    output logic tick
);

  logic [$clog2(DIVISOR-1):0] cnt;

  always_ff @(posedge clk) begin
    if (!rst_n) cnt <= '0;
    else if (clr) cnt <= '0;
    else cnt <= (cnt == $bits(cnt)'(DIVISOR - 1)) ? '0 : cnt + 1'b1;
  end

  assign tick = (cnt == $bits(cnt)'(DIVISOR - 1));

endmodule
