module uart #(
    parameter int CLK_FREQ_HZ = 100_000_000,
    parameter int BAUD_RATE   = 115_200,
    parameter int OVERSAMPLE  = 16,
    parameter int DATA_BITS   = 8,
    parameter int BaudW       = 16
) (
    input logic clk,
    input logic rst_n,

    input logic parity_en,
    input logic parity_odd,
    input logic [BaudW-1:0] baud_div,

    input logic [DATA_BITS-1:0] tx_data,
    input logic tx_valid,
    output logic tx_ready,
    output logic tx_serial,

    input logic rx_serial,
    output logic [DATA_BITS-1:0] rx_data,
    output logic rx_valid,
    output logic rx_error
);

  uart_tx #(
      .CLK_FREQ_HZ(CLK_FREQ_HZ),
      .BAUD_RATE  (BAUD_RATE),
      .DATA_BITS  (DATA_BITS),
      .BaudW      (BaudW)
  ) u_tx (
      .clk(clk),
      .rst_n(rst_n),
      .tx_data(tx_data),
      .tx_valid(tx_valid),
      .parity_en(parity_en),
      .parity_odd(parity_odd),
      .baud_div(baud_div),
      .tx_ready(tx_ready),
      .tx_serial(tx_serial)
  );

  uart_rx #(
      .CLK_FREQ_HZ(CLK_FREQ_HZ),
      .BAUD_RATE  (BAUD_RATE),
      .OVERSAMPLE (OVERSAMPLE),
      .DATA_BITS  (DATA_BITS),
      .BaudW      (BaudW)
  ) u_rx (
      .clk(clk),
      .rst_n(rst_n),
      .rx_serial(rx_serial),
      .parity_en(parity_en),
      .parity_odd(parity_odd),
      .baud_div(baud_div),
      .rx_data(rx_data),
      .rx_valid(rx_valid),
      .rx_error(rx_error)
  );

endmodule
