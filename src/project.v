/*
 * Copyright (c) 2026 Drew Babel
 * SPDX-License-Identifier: Apache-2.0
 *
 * TinyTapeout tile wrapper for the UART (drewbabel/uart).
 * This file is pure plumbing: it maps the UART's ports onto the fixed
 * 8-in / 8-out / 8-bidirectional TinyTapeout pin interface. The UART
 * design itself lives in uart.sv + submodules.
 *
 * PIN MAP (also mirrored in info.yaml):
 *   ui_in[7:0]   -> tx_data[7:0]   byte to transmit (parallel load)
 *   uio_in[0]    -> rx_serial      serial receive line   (bidir pin as input)
 *   uio_in[1]    -> tx_valid       assert to send tx_data (bidir pin as input)
 *   uo_out[7:0]  <- rx_data[7:0]   last received byte
 *   uio_out[2]   <- tx_serial      serial transmit line
 *   uio_out[3]   <- tx_ready       TX can accept a new byte
 *   uio_out[4]   <- rx_valid       a byte was received (1-cycle pulse)
 *   uio_out[5]   <- rx_error       framing error (1-cycle pulse)
 *   uio[6], uio[7]                 unused
 */

`default_nettype none

module tt_um_drewbabel_uart (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (1 = drive output)
    input  wire       ena,      // high when the design is selected (unused)
    input  wire       clk,      // clock
    input  wire       rst_n     // active-low reset
);

  // --- UART <-> pin wiring ---
  wire       tx_valid  = uio_in[1];
  wire       rx_serial = uio_in[0];
  wire       tx_ready;
  wire       tx_serial;
  wire [7:0] rx_data;
  wire       rx_valid;
  wire       rx_error;

  uart #(
      .CLK_FREQ_HZ(50_000_000),  // FINALIZE at submission: must match the TT clock you request
      .BAUD_RATE  (115_200),
      .OVERSAMPLE (16),
      .DATA_BITS  (8)
  ) u_uart (
      .clk      (clk),
      .rst_n    (rst_n),
      // TX
      .tx_data  (ui_in),
      .tx_valid (tx_valid),
      .tx_ready (tx_ready),
      .tx_serial(tx_serial),
      // RX
      .rx_serial(rx_serial),
      .rx_data  (rx_data),
      .rx_valid (rx_valid),
      .rx_error (rx_error)
  );

  // Dedicated outputs: the received byte
  assign uo_out = rx_data;

  // Bidirectional pins: [5:2] driven as status/serial outputs, rest inputs
  assign uio_out[0] = 1'b0;
  assign uio_out[1] = 1'b0;
  assign uio_out[2] = tx_serial;
  assign uio_out[3] = tx_ready;
  assign uio_out[4] = rx_valid;
  assign uio_out[5] = rx_error;
  assign uio_out[6] = 1'b0;
  assign uio_out[7] = 1'b0;
  assign uio_oe     = 8'b0011_1100;  // 1 = output: pins 2,3,4,5

  // Silence unused-signal warnings
  wire _unused = &{ena, uio_in[7:2], 1'b0};

endmodule
