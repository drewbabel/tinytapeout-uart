![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# tinytapeout-uart

A configurable UART with transmit and receive FIFOs and a memory-mapped AMBA-APB register block, hardened for the Tiny Tapeout SKY130 (ttsky26c) shuttle.

The transmitter serializes a parallel byte behind start and stop bits (8N1, with optional parity). The receiver oversamples the incoming line at 16x, recovers each byte with mid-bit sampling, and flags framing and parity errors. A `tick_gen` divides the 50 MHz system clock down to the baud rate and the receiver's oversample rate. A two-flop `synchronizer` guards the asynchronous receive line against metastability across the clock-domain crossing, giving a clock-mismatch tolerance of about +/-4%.

A 16-deep `sync_fifo` on each path decouples the host from the serial timing, so the host bursts bytes in through `tx_push` and drains them out through `rx_pop` without tracking the UART cycle by cycle. Both strobes are two-flop synchronized and rising-edge detected inside the tile, so a host pin pulse of any width enqueues or dequeues exactly one byte. A small loader FSM hands buffered bytes from the TX FIFO to `uart_tx` whenever the transmitter is ready, and received bytes flow from `uart_rx` into the RX FIFO. The whole tile is pin-muxed onto the Tiny Tapeout `ui`/`uo`/`uio` bus.

A memory-mapped register block makes the tile programmable at runtime over the pins it already has. A `csr_pin_adapter` shifts a 12-bit frame of a read/write bit, an address, and a data byte in over three reused pins, then drives it as one AMBA-APB transaction into `apb_csr`, a small APB-slave register file. The registers turn on an internal loopback so the tile can exercise itself with no host, select even or odd parity, set a runtime baud divisor, and expose the FIFO status flags for readback.

![Tile block diagram](docs/uart_tile_block.svg)

## Pin map

| Signal | Direction | Width | Description |
|--------|-----------|-------|-------------|
| `ui[7:0]` | in | 8 | `tx_data`, byte to enqueue for transmit (`ui[0]` doubles as `csr_mosi` in CSR mode) |
| `uio[0]` | in | 1 | `rx_serial`, receive line (idle high) |
| `uio[1]` | in | 1 | `tx_push`, rising edge pushes `ui_in` into the TX FIFO (doubles as `csr_sclk` in CSR mode) |
| `uio[2]` | in | 1 | `rx_pop`, rising edge pops a byte from the RX FIFO |
| `uio[7]` | in | 1 | `csr_mode`, hold high to shift a CSR frame in |
| `uo[7:0]` | out | 8 | `rx_data`, RX FIFO read data, or CSR read data after a register read |
| `uio[3]` | out | 1 | `tx_serial`, transmit line (idle high) |
| `uio[4]` | out | 1 | `tx_full`, TX FIFO full |
| `uio[5]` | out | 1 | `rx_empty`, RX FIFO empty |
| `uio[6]` | out | 1 | `rx_error`, framing or parity error (one-cycle pulse, latched in `STATUS`) |

`tx_push` and `rx_pop` pass through a two-flop synchronizer and a rising-edge detector, so each pulse acts once no matter how long the host holds the pin. Hold `ui_in` stable from the `tx_push` rising edge until a few clocks after the pin is released. A popped byte appears on `uo_out` about six clocks after the `rx_pop` rising edge and stays until the next pop.

## Configuration registers

The register block is an AMBA-APB slave. A full parallel bus will not fit the one spare pin, so the host shifts each transaction in serially. It holds `csr_mode` high and clocks a 12-bit frame on `csr_sclk`, MSB first, with each bit on `csr_mosi`. The frame carries one read/write bit, then a 3-bit address, then a byte of data. The adapter synchronizes the asynchronous shift clock into the tile domain, assembles the frame, and issues a single APB access. Keep `csr_mode` high for at least ten clocks after the twelfth `csr_sclk` rising edge so the transaction lands before the adapter resets. A read holds its byte on `uo_out` until `csr_mode` drops or the next frame starts shifting.

| Addr | Name | Access | Contents |
|------|------|--------|----------|
| 0 | `CTRL` | R/W | bit0 `loopback_en`, bit1 `parity_en`, bit2 `parity_odd` (a write clears the sticky `STATUS` bits) |
| 1 | `STATUS` | R | bit0 `tx_full`, bit1 `tx_empty`, bit2 `rx_empty`, bit3 sticky `rx_error`, bit4 sticky `rx_overflow` |
| 2 | `SCRATCH` | R/W | 8-bit scratch register |
| 3 | `BAUD_LO` | R/W | baud divisor `[7:0]` |
| 4 | `BAUD_HI` | R/W | baud divisor `[15:8]` |

The baud divisor is `clock_hz / baud`, so 115200 baud at the hardened 50 MHz clock is a divisor of 434. A divisor of 0 (the reset value) selects the compile-time default of 434. The receiver rounds the divisor to the nearest multiple of 16 for its oversample period, so its effective bit rate is `clock_hz / (16 * round(divisor / 16))`: keep the divisor within about 4% of a multiple of 16, which below a divisor of roughly 250 means using multiples of 16 exactly (the default 434 rounds to 432, well inside tolerance). Each frame latches the parity and baud configuration as it starts, and the sticky `STATUS` bits hold framing, parity, and RX-overflow events until a `CTRL` write clears them. Reconfigure the divisor while the link is quiet, writing `BAUD_LO` then `BAUD_HI`.

## Verification

| Test | Method |
|------|--------|
| `test/test.py` | top level through the tile pins. 100-byte randomized loopback, framing error, data-value sweep, +/-4% baud tolerance, start-glitch rejection, back-to-back frames, CSR write/read + loopback + parity + runtime baud over the serial frame interface, held-strobe edge-detect checks, `tx_full` backpressure, pop-on-empty, mid-frame reset recovery, sticky error/overflow set and clear, post-overflow FIFO drain integrity, parity-error sticky chain, mid-frame baud reconfiguration, minimum divisor, `ui_in` hold contract, pop gating in CSR mode, CTRL/BAUD readback, unmapped addresses, CSR mode-exit strobe race |
| `test/csr` | APB register block driven directly, plus a serial-frame to APB round-trip through the adapter |
| `test/uart` | parity (even and odd, good and error) and a runtime baud divisor through loopback |

The gate-level run (`make GATES=yes`) executes the full `test/test.py` suite against the hardened netlist, CSR path included.

Run from `test/`:

```
make                             # top-level cocotb tests
make GATES=yes                   # gate-level simulation against the hardened netlist
make -C csr                      # CSR register block (isolation)
make -C csr -f Makefile.adapter  # CSR serial adapter plus register block (integration)
make -C uart                     # parity and runtime baud
```

## Results

A byte pushed into the TX FIFO is shifted out on `tx_serial` as an 8N1 frame, recovered by the receiver into the RX FIFO, and read back on `uo_out`.

![Loopback waveform](docs/uart_waveform.svg)

A serial CSR write shifts a 12-bit frame in on `csr_sclk` and `csr_mosi`, and the adapter drives one APB write into the register block.

![CSR write waveform](docs/uart_csr_waveform.svg)

## Resources

- [Tiny Tapeout](https://tinytapeout.com)
- [FAQ](https://tinytapeout.com/faq/)
- [Submit your design to a shuttle](https://app.tinytapeout.com/)
