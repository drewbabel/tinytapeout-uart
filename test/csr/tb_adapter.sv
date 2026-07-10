`default_nettype none
`timescale 1ns / 1ps

// Integration testbench: csr_pin_adapter (APB master) wired to apb_csr (slave)
// Drives the serial CSR pins and checks the transaction reaches the register file
module tb_adapter ();

  initial begin
    $dumpfile("tb_adapter.fst");
    $dumpvars(0, tb_adapter);
    #1;
  end

  localparam ADDR_W = 3;
  localparam DATA_W = 8;

  logic clk;
  logic rst_n;

  logic csr_mode;
  logic csr_sclk;
  logic csr_mosi;

  logic tx_full;
  logic tx_empty;
  logic rx_empty;
  logic rx_error;

  logic loopback_en;
  logic [DATA_W-1:0] rdata_out;
  logic read_valid;

  logic psel, penable, pwrite, pready;
  logic [ADDR_W-1:0] paddr;
  logic [DATA_W-1:0] pwdata, prdata;

  csr_pin_adapter #(
      .ADDR_W(ADDR_W),
      .DATA_W(DATA_W)
  ) u_adapter (
      .clk       (clk),
      .rst_n     (rst_n),
      .csr_mode  (csr_mode),
      .csr_sclk  (csr_sclk),
      .csr_mosi  (csr_mosi),
      .psel      (psel),
      .penable   (penable),
      .pwrite    (pwrite),
      .paddr     (paddr),
      .pwdata    (pwdata),
      .prdata    (prdata),
      .pready    (pready),
      .rdata_out (rdata_out),
      .read_valid(read_valid)
  );

  apb_csr #(
      .ADDR_W(ADDR_W),
      .DATA_W(DATA_W)
  ) u_csr (
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
      .tx_full    (tx_full),
      .tx_empty   (tx_empty),
      .rx_empty   (rx_empty),
      .rx_error   (rx_error)
  );

endmodule
