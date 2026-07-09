![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# tinytapeout-uart

A configurable UART with transmit and receive FIFOs, hardened for the Tiny Tapeout SKY130 (ttsky26c) shuttle.

The transmitter serializes a parallel byte behind start and stop bits (8N1); the receiver oversamples the incoming line at 16x, recovers each byte with mid-bit sampling, and flags framing errors. A `tick_gen` divides the 50 MHz system clock down to the baud rate and the receiver's oversample rate, and a two-flop `synchronizer` guards the asynchronous receive line against metastability, giving a clock-mismatch tolerance of about +/-4%.

A 16-deep `sync_fifo` on each path decouples the host from the serial timing, so the host bursts bytes in through `tx_push` and drains them out through `rx_pop` without tracking the UART cycle by cycle. A small loader FSM hands buffered bytes from the TX FIFO to `uart_tx` whenever the transmitter is ready, and received bytes flow from `uart_rx` into the RX FIFO. The whole tile is pin-muxed onto the Tiny Tapeout `ui`/`uo`/`uio` bus.

The design is verified with a randomized self-checking cocotb testbench that loops 100 random bytes through the full TX-to-RX path and checks each against the reference stream, plus a framing-error case; the `uart_tx` and `uart_rx` cores each carry a SymbiYosys formal proof in the standalone [uart](https://github.com/drewbabel/uart) repo this design is built from.

![Tile block diagram](docs/uart_tile_block.svg)

## Pin map

| Signal | Direction | Width | Description |
|--------|-----------|-------|-------------|
| `ui[7:0]` | in | 8 | `tx_data`, byte to enqueue for transmit |
| `uio[1]` | in | 1 | `tx_push`, pulse to push `ui_in` into the TX FIFO |
| `uio[2]` | in | 1 | `rx_pop`, pulse to pop a byte from the RX FIFO |
| `uio[0]` | in | 1 | `rx_serial`, receive line (idle high) |
| `uo[7:0]` | out | 8 | `rx_data`, RX FIFO read data |
| `uio[3]` | out | 1 | `tx_serial`, transmit line (idle high) |
| `uio[4]` | out | 1 | `tx_full`, TX FIFO full |
| `uio[5]` | out | 1 | `rx_empty`, RX FIFO empty |
| `uio[6]` | out | 1 | `rx_error`, framing error |

## Clock and area

Hardened at 50 MHz (`clock_hz: 50000000`, `CLOCK_PERIOD: 20`), giving `ClksPerBit = 434` at 115200 baud. Occupies a 1x2 tile: the pins fit a single tile, but the two 16-deep FIFOs push a 1x1 over utilization.

## Verification

| Test | Method |
|------|--------|
| `test.py` | cocotb FIFO loopback smoke test |
| `test_hardened.py` | 100-byte randomized self-checking loopback + framing-error case |

Run from `test/`:

```
make            # run the cocotb tests
make GATES=yes  # gate-level simulation against the hardened netlist
```

## Results

Internal loopback of `0x5A`: the byte is pushed into the TX FIFO, shifted out on `tx_serial` as an 8N1 frame, recovered by the receiver into the RX FIFO (`rx_empty` falls), and read back on `uo_out` when the host pulses `rx_pop`.

![Loopback waveform](docs/uart_waveform.svg)

## Resources

- [Tiny Tapeout](https://tinytapeout.com)
- [FAQ](https://tinytapeout.com/faq/)
- [Submit your design to a shuttle](https://app.tinytapeout.com/)
