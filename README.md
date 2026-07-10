# tinytapeout-uart

[![gds](https://github.com/drewbabel/tinytapeout-uart/actions/workflows/gds.yaml/badge.svg)](https://github.com/drewbabel/tinytapeout-uart/actions/workflows/gds.yaml) [![test](https://github.com/drewbabel/tinytapeout-uart/actions/workflows/test.yaml/badge.svg)](https://github.com/drewbabel/tinytapeout-uart/actions/workflows/test.yaml) [![docs](https://github.com/drewbabel/tinytapeout-uart/actions/workflows/docs.yaml/badge.svg)](https://github.com/drewbabel/tinytapeout-uart/actions/workflows/docs.yaml)

A configurable FIFO-buffered UART with an AMBA APB register block, written in SystemVerilog and hardened on SkyWater SKY130 for the Tiny Tapeout ttsky26c shuttle.

The transmitter serializes each byte behind start and stop bits, with optional even or odd parity. The receiver oversamples the line at 16x, recovers each byte with mid-bit sampling that resynchronizes on every start edge, and flags framing and parity errors. A `tick_gen` divides the 50 MHz system clock to the baud rate, and a two-flop `synchronizer` guards each asynchronous input against metastability.

A 16-deep `sync_fifo` on each path decouples the host interface from the serial timing. `tx_push` enqueues the byte on `ui_in` into the TX FIFO, a loader FSM hands buffered bytes to `uart_tx` whenever the transmitter is ready, and received bytes drain through `rx_pop`. Both strobes are two-flop synchronized and rising-edge detected, so a pulse of any width moves exactly one byte.

A `csr_pin_adapter` shifts a 12-bit serial frame in over three pins and drives it as one APB transaction into `apb_csr`, a register file that controls internal loopback, parity, and a runtime baud divisor, and exposes FIFO and error status.

Every block is exercised through the tile pins by a self-checking cocotb suite, and CI runs the same suite against the hardened gate-level netlist.

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

Each strobe acts once per rising edge regardless of pulse width. Hold `ui_in` stable from the `tx_push` rising edge until a few clocks after release. A popped byte appears on `uo_out` about six clocks after the `rx_pop` rising edge and holds until the next pop.

## Configuration registers

The register block is an AMBA APB slave reached serially. With `csr_mode` held high, the host clocks a 12-bit frame of a read/write bit, a 3-bit address, and a data byte on `csr_sclk` and `csr_mosi`, MSB first. The adapter synchronizes the shift clock into the tile domain, assembles the frame, and issues a single APB access. Keep `csr_mode` high for at least ten clocks after the final `csr_sclk` rising edge. A read holds its byte on `uo_out` until `csr_mode` drops or the next frame starts.

| Addr | Name | Access | Contents |
|------|------|--------|----------|
| 0 | `CTRL` | R/W | bit0 `loopback_en`, bit1 `parity_en`, bit2 `parity_odd` (a write clears the sticky `STATUS` bits) |
| 1 | `STATUS` | R | bit0 `tx_full`, bit1 `tx_empty`, bit2 `rx_empty`, bit3 sticky `rx_error`, bit4 sticky `rx_overflow` |
| 2 | `SCRATCH` | R/W | 8-bit scratch register |
| 3 | `BAUD_LO` | R/W | baud divisor `[7:0]` |
| 4 | `BAUD_HI` | R/W | baud divisor `[15:8]` |

The baud divisor is `clock_hz / baud`. At the 50 MHz tile clock, 115200 baud is a divisor of 434, and a divisor of 0 (the reset value) selects the compile-time default of 434. The receiver rounds the divisor to the nearest multiple of 16 for its oversample period, giving an effective bit rate of `clock_hz / (16 * round(divisor / 16))`, so keep the divisor within 4% of a multiple of 16. Each frame latches the parity and baud configuration as it starts, and the sticky `STATUS` bits hold error and overflow events until a `CTRL` write clears them. Reconfigure the divisor while the link is quiet, writing `BAUD_LO` then `BAUD_HI`.

## Verification

| Suite | Method |
|-------|--------|
| `test/test.py` | Self-checking cocotb suite through the tile pins, run at RTL and gate level |
| `test/csr` | APB register block driven directly + serial-frame round trip through the adapter |
| `test/uart` | Parity and runtime baud through a `uart` core loopback |

The top-level suite covers randomized loopback, a data-value sweep, framing and parity errors, a 4% baud mismatch in both directions, start-glitch rejection, back-to-back frames, and every CSR register through the serial frame interface. Strobe handling is checked with held pins, the `ui_in` hold contract, pops on an empty FIFO, and pops during CSR mode. FIFO behavior is checked with `tx_full` backpressure, an overflow followed by an in-order drain of the retained bytes, and a mid-frame reset. The suite also covers mid-frame baud writes, the minimum divisor, sticky error set and clear, unmapped addresses, and the CSR mode-exit strobe race.

The gate-level run (`make GATES=yes`) executes the full top-level suite against the hardened netlist.

## Results

A byte pushed into the TX FIFO is shifted out on `tx_serial` as an 8N1 frame, recovered by the receiver into the RX FIFO, and read back on `uo_out`.

![Loopback waveform](docs/uart_waveform.svg)

A serial CSR write shifts a 12-bit frame in on `csr_sclk` and `csr_mosi`, and the adapter drives one APB write into the register block.

![CSR write waveform](docs/uart_csr_waveform.svg)

## Building and running

Run from `test/`:

```
make                             # top-level cocotb suite
make GATES=yes                   # gate-level simulation against the hardened netlist
make -C csr                      # CSR register block in isolation
make -C csr -f Makefile.adapter  # CSR serial adapter plus register block
make -C uart                     # parity and runtime baud
```

### Tool versions

Icarus Verilog 13.0, cocotb 2.0.1, and Verilator for lint. The GDS flow runs LibreLane 3.0.3 on the SKY130A PDK.

## Resources

- [Tiny Tapeout](https://tinytapeout.com)
- [FAQ](https://tinytapeout.com/faq/)
- [Submit your design to a shuttle](https://app.tinytapeout.com/)
