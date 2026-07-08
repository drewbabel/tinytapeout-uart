module rptr_empty #(
    parameter  int DEPTH = 16,
    localparam int AW    = $clog2(DEPTH)  // Address width: pointer = AW+1 bits (extra wrap bit)
) (
    input  logic          rd_clk,
    input  logic          rd_rst_n,
    input  logic          rd_en,
    input  logic [  AW:0] wr_gray_sync,  // Synced into write domain
    output logic          empty,
    output logic [AW-1:0] rd_addr,
    output logic [  AW:0] rd_gray
);

  logic [AW:0] rd_ptr;  // Binary version
  logic [AW:0] rd_ptr_next;

  always @(posedge rd_clk) begin
    if (!rd_rst_n) begin
      rd_ptr  <= '0;
      rd_gray <= '0;
    end else begin
      rd_ptr  <= rd_ptr_next;
      rd_gray <= rd_ptr_next ^ (rd_ptr_next >> 1);  // Gray version: registered due to CDC
    end
  end

  assign rd_addr = rd_ptr[AW-1:0];
  assign rd_ptr_next = rd_ptr + (rd_en && !empty);  // +1 on accepted read, else +0
  assign empty = (rd_gray == wr_gray_sync);

`ifdef FORMAL
  initial begin
    assume (rd_ptr == '0);
    assume (rd_gray == '0);
  end
  always_comb assert (rd_gray == (rd_ptr ^ (rd_ptr >> 1)));
`endif

endmodule



