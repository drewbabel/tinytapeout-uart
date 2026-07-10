`default_nettype none
`timescale 1ns / 1ps

// Feature testbench for the uart core: parity + runtime baud.
module tb_uart ();

  initial begin
    $dumpfile("tb_uart.fst");
    $dumpvars(0, tb_uart);
    #1;
  end

  localparam int CLK_FREQ_HZ = 50_000_000;
  localparam int BAUD_RATE = 115_200;
  localparam int OVERSAMPLE = 16;
  localparam int DATA_BITS = 8;
  localparam int BaudW = 16;

  logic clk;
  logic rst_n;
  logic parity_en;
  logic parity_odd;
  logic [BaudW-1:0] baud_div;
  logic [DATA_BITS-1:0] tx_data;
  logic tx_valid;
  logic tx_ready;
  logic tx_serial;
  logic rx_serial;
  logic [DATA_BITS-1:0] rx_data;
  logic rx_valid;
  logic rx_error;

  uart #(
      .CLK_FREQ_HZ(CLK_FREQ_HZ),
      .BAUD_RATE  (BAUD_RATE),
      .OVERSAMPLE (OVERSAMPLE),
      .DATA_BITS  (DATA_BITS),
      .BaudW      (BaudW)
  ) dut (
      .clk       (clk),
      .rst_n     (rst_n),
      .parity_en (parity_en),
      .parity_odd(parity_odd),
      .baud_div  (baud_div),
      .tx_data   (tx_data),
      .tx_valid  (tx_valid),
      .tx_ready  (tx_ready),
      .tx_serial (tx_serial),
      .rx_serial (rx_serial),
      .rx_data   (rx_data),
      .rx_valid  (rx_valid),
      .rx_error  (rx_error)
  );

endmodule
