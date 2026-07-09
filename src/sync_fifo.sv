module sync_fifo #(
    parameter int WIDTH = 8,
    parameter int DEPTH = 16
) (
    input logic clk,
    input logic rst_n,
    input logic wr_en,
    input logic rd_en,
    input logic [WIDTH-1:0] wr_data,
    output logic [WIDTH-1:0] rd_data,
    output logic full,
    output logic empty
);

  localparam int AW = $clog2(DEPTH);  // address width: pointer = Aw+1 bits (extra wrap bit)

  logic [WIDTH-1:0] mem[DEPTH];
  logic [AW:0] wr_ptr;
  logic [AW:0] rd_ptr;

  logic [AW-1:0] wr_addr;
  logic [AW-1:0] rd_addr;
  assign wr_addr = wr_ptr[AW-1:0];
  assign rd_addr = rd_ptr[AW-1:0];

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      wr_ptr  <= '0;
      rd_ptr  <= '0;
      rd_data <= '0;
    end else begin
      if (wr_en && !full) begin
        mem[wr_addr] <= wr_data;
        wr_ptr <= wr_ptr + 1'b1;
      end
      if (rd_en && !empty) begin
        rd_data <= mem[rd_addr];
        rd_ptr  <= rd_ptr + 1'b1;
      end
    end
  end

  assign full  = (wr_ptr[AW] != rd_ptr[AW]) && (wr_addr == rd_addr);
  assign empty = (wr_ptr == rd_ptr);

endmodule
