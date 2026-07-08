module fifomem #(
    parameter int WIDTH = 8,
    parameter int DEPTH = 16
) (
    input logic                     wr_clk,
    input logic                     wr_en,
    input logic                     full,
    input logic [$clog2(DEPTH)-1:0] wr_addr,
    input logic [        WIDTH-1:0] wr_data,

    input  logic                     rd_clk,
    input  logic                     rd_en,
    input  logic                     empty,
    input  logic [$clog2(DEPTH)-1:0] rd_addr,
    output logic [        WIDTH-1:0] rd_data
);

  logic [WIDTH-1:0] mem[DEPTH];

  always_ff @(posedge wr_clk) begin
    if (wr_en && !full) begin
      mem[wr_addr] <= wr_data;
    end
  end

  always_ff @(posedge rd_clk) begin
    if (rd_en && !empty) begin
      rd_data <= mem[rd_addr];
    end
  end

endmodule
