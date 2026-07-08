module wptr_full #(
    parameter  int DEPTH = 16,
    localparam int AW    = $clog2(DEPTH)  // Address width: pointer = AW+1 bits (extra wrap bit)
) (
    input  logic          wr_clk,
    input  logic          wr_rst_n,
    input  logic          wr_en,
    input  logic [  AW:0] rd_gray_sync,  // Synced into write domain
    output logic          full,
    output logic [AW-1:0] wr_addr,
    output logic [  AW:0] wr_gray
);

  logic [AW:0] wr_ptr;  // Binary version
  logic [AW:0] wr_ptr_next;

  always @(posedge wr_clk) begin
    if (!wr_rst_n) begin
      wr_ptr  <= '0;
      wr_gray <= '0;
    end else begin
      wr_ptr  <= wr_ptr_next;
      wr_gray <= wr_ptr_next ^ (wr_ptr_next >> 1);  // Gray version: registered due to CDC
    end
  end

  assign wr_addr = wr_ptr[AW-1:0];
  assign wr_ptr_next = wr_ptr + (wr_en && !full);  // +1 on accepted write, else +0
  assign full = (wr_gray == {~rd_gray_sync[AW:AW-1], rd_gray_sync[AW-2:0]});

`ifdef FORMAL
  initial begin
    assume (wr_ptr == '0);
    assume (wr_gray == '0);
  end
  always_comb assert (wr_gray == (wr_ptr ^ (wr_ptr >> 1)));
`endif

endmodule
