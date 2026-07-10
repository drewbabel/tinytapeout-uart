`default_nettype none
`timescale 1ns / 1ps

// Isolation testbench for apb_csr (drives the APB slave directly)
module tb_csr ();

  initial begin
    $dumpfile("tb_csr.fst");
    $dumpvars(0, tb_csr);
    #1;
  end

  localparam int AddrW = 3;
  localparam int DataW = 8;

  logic clk;
  logic rst_n;

  logic psel;
  logic penable;
  logic pwrite;
  logic [AddrW-1:0] paddr;
  logic [DataW-1:0] pwdata;
  logic [DataW-1:0] prdata;
  logic pready;

  logic loopback_en;
  logic parity_en;
  logic parity_odd;
  logic [2*DataW-1:0] baud_div;

  logic tx_full;
  logic tx_empty;
  logic rx_empty;
  logic rx_error;

  apb_csr #(
      .ADDR_W(AddrW),
      .DATA_W(DataW)
  ) dut (
      .clk        (clk),
      .rst_n      (rst_n),
      .psel       (psel),
      .penable    (penable),
      .pwrite     (pwrite),
      .paddr      (paddr),
      .pwdata     (pwdata),
      .prdata     (prdata),
      .pready     (pready),
      .loopback_en(loopback_en),
      .parity_en  (parity_en),
      .parity_odd (parity_odd),
      .baud_div   (baud_div),
      .tx_full    (tx_full),
      .tx_empty   (tx_empty),
      .rx_empty   (rx_empty),
      .rx_error   (rx_error)
  );

endmodule
