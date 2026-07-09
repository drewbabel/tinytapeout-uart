<!---
Datasheet source. Drafted from the design; review the prose before you submit,
especially the clock frequency and the demo procedure once your hardware is decided.
-->

## How it works

This is an 8-bit UART (serial transmitter and receiver, 8N1 framing) with a 16-deep
synchronous FIFO on both the transmit and receive paths.

- **Transmit:** the host presents a byte on `ui_in[7:0]` and pulses `tx_push` (`uio[1]`) to
  enqueue it into the TX FIFO. A small loader hands buffered bytes to the UART transmitter
  one at a time whenever the transmitter is ready, shifting each out on `tx_serial` (`uio[3]`)
  as a start bit, 8 data bits (LSB first), and a stop bit. `tx_full` (`uio[4]`) signals the
  FIFO is full and the host should stop pushing.
- **Receive:** the receiver oversamples `rx_serial` (`uio[0]`) at 16x, recovers each byte, and
  pushes it into the RX FIFO. `rx_empty` (`uio[5]`) is low when a byte is available; the host
  pulses `rx_pop` (`uio[2]`) to read the oldest byte, which appears on `uo_out[7:0]` the
  following clock. `rx_error` (`uio[6]`) pulses on a framing error.

The receiver uses a two-flop synchronizer on the incoming serial line and per-frame
resynchronization with mid-bit sampling, giving a clock-mismatch tolerance of about +/-4%.

## How to test

Drive the design from a serial source at a baud rate matching the hardened clock
(`clock_hz` divided down to the baud rate). To verify TX and RX together with no external
host, tie `tx_serial` (`uio[3]`) back to `rx_serial` (`uio[0]`): push a byte via `ui_in` +
`tx_push`, wait for `rx_empty` to go low, pulse `rx_pop`, and confirm the same byte appears
on `uo_out`. For a real link, connect `tx_serial`/`rx_serial` to a USB-to-serial adapter
(e.g. FT232) at the matched baud and exchange bytes with a terminal.

## External hardware

A USB-to-serial (UART) adapter such as an FT232RL breakout, to connect the chip's serial
lines to a host terminal. None required for the internal loopback self-test.
