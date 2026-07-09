/*
 * Copyright (c) 2026 Drew Babel
 * SPDX-License-Identifier: Apache-2.0
 *
 * PIN MAP:
 *   ui_in[7:0]  -> tx_data[7:0]  byte to enqueue for transmit
 *   uio_in[0]   -> rx_serial     serial receive line
 *   uio_in[1]   -> tx_push       pulse to push ui_in into TX FIFO
 *   uio_in[2]   -> rx_pop        pulse to pop a byte from RX FIFO
 *   uo_out[7:0] <- rx_data[7:0]  RX FIFO read data
 *   uio_out[3]  <- tx_serial     serial transmit line
 *   uio_out[4]  <- tx_full       TX FIFO full
 *   uio_out[5]  <- rx_empty      RX FIFO empty
 *   uio_out[6]  <- rx_error      framing error
 *   uio_out[7]                   FREE
 *
 * DATA FLOW
 *   TX: host pulses tx_push -> byte enters TX FIFO. A 2-state loader pops one
 *       byte whenever the UART is ready and drives it into the UART TX.
 *   RX: UART asserts rx_valid on a received byte -> byte enters RX FIFO.
 *       Host pulses rx_pop -> byte appears on uo_out next cycle.
 */

`default_nettype none

module tt_um_drewbabel_uart (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);

  logic       rx_serial;
  logic       tx_push;
  logic       rx_pop;
  assign rx_serial = uio_in[0];
  assign tx_push   = uio_in[1];
  assign rx_pop    = uio_in[2];

  logic [7:0] tx_fifo_dout;
  logic       tx_full;
  logic       tx_empty;
  logic       tx_fifo_rd;

  sync_fifo #(
      .WIDTH(8),
      .DEPTH(16)
  ) tx_fifo (
      .clk    (clk),
      .rst_n  (rst_n),
      .wr_en  (tx_push),
      .rd_en  (tx_fifo_rd),
      .wr_data(ui_in),
      .rd_data(tx_fifo_dout),
      .full   (tx_full),
      .empty  (tx_empty)
  );

  logic       uart_tx_ready;
  logic       uart_tx_serial;
  logic       uart_tx_valid;
  logic [7:0] uart_rx_data;
  logic       uart_rx_valid;
  logic       uart_rx_error;

  uart #(
      .CLK_FREQ_HZ(50_000_000),  // FINALIZE at submission: match the TT clock you request
      .BAUD_RATE  (115_200),
      .OVERSAMPLE (16),
      .DATA_BITS  (8)
  ) u_uart (
      .clk      (clk),
      .rst_n    (rst_n),
      .tx_data  (tx_fifo_dout),
      .tx_valid (uart_tx_valid),
      .tx_ready (uart_tx_ready),
      .tx_serial(uart_tx_serial),
      .rx_serial(rx_serial),
      .rx_data  (uart_rx_data),
      .rx_valid (uart_rx_valid),
      .rx_error (uart_rx_error)
  );

  localparam T_IDLE = 2'd0, T_READ = 2'd1, T_SEND = 2'd2;
  logic [1:0] tstate;

  always @(*) begin
    tx_fifo_rd    = (tstate == T_READ);
    uart_tx_valid = (tstate == T_SEND);
  end

  always @(posedge clk) begin
    if (!rst_n) tstate <= T_IDLE;
    else begin
      case (tstate)
        T_IDLE:  if (!tx_empty && uart_tx_ready) tstate <= T_READ;
        T_READ:  tstate <= T_SEND;
        T_SEND:  tstate <= T_IDLE;
        default: tstate <= T_IDLE;
      endcase
    end
  end

  logic [7:0] rx_fifo_dout;
  logic       rx_empty;
  logic       rx_full_unused;

  sync_fifo #(
      .WIDTH(8),
      .DEPTH(16)
  ) rx_fifo (
      .clk    (clk),
      .rst_n  (rst_n),
      .wr_en  (uart_rx_valid),
      .rd_en  (rx_pop),
      .wr_data(uart_rx_data),
      .rd_data(rx_fifo_dout),
      .full   (rx_full_unused),
      .empty  (rx_empty)
  );

  assign uo_out     = rx_fifo_dout;
  assign uio_out[0] = 1'b0;
  assign uio_out[1] = 1'b0;
  assign uio_out[2] = 1'b0;
  assign uio_out[3] = uart_tx_serial;
  assign uio_out[4] = tx_full;
  assign uio_out[5] = rx_empty;
  assign uio_out[6] = uart_rx_error;
  assign uio_out[7] = 1'b0;
  assign uio_oe     = 8'b0111_1000;  // 1 = output: pins 3,4,5,6

  logic _unused;
  assign _unused = &{ena, uio_in[7:3], rx_full_unused, 1'b0};

endmodule
