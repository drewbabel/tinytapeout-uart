# SPDX-License-Identifier: Apache-2.0
#
# SMOKE TEST ONLY

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

# Pin map (see src/project.sv)
RX_SERIAL = 0  # uio_in[0]
TX_PUSH = 1    # uio_in[1]
RX_POP = 2     # uio_in[2]
TX_SERIAL = 3  # uio_out[3]
TX_FULL = 4    # uio_out[4]
RX_EMPTY = 5   # uio_out[5]
RX_ERROR = 6   # uio_out[6]


def bit(sig, i, default=1):
    """Return bit i of a signal, resolving X/Z to `default` (idle line = 1)."""
    s = str(sig.value)[::-1]  # LSB-first
    if i >= len(s):
        return default
    c = s[i]
    return int(c) if c in "01" else default


@cocotb.test()
async def test_fifo_loopback(dut):
    dut._log.info("Start: TX FIFO -> UART -> loop -> RX -> RX FIFO smoke test")

    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())  # 50 MHz

    # Reset
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    test_byte = 0x5A

    # Push one byte into the TX FIFO (one-cycle pulse)
    dut.ui_in.value = test_byte
    dut.uio_in.value = 1 << TX_PUSH
    await RisingEdge(dut.clk)
    dut.uio_in.value = 0

    # Run the serial loopback (TX line -> RX line) until the RX FIFO reports data
    got_data = False
    for _ in range(8000):
        await RisingEdge(dut.clk)
        tx = bit(dut.uio_out, TX_SERIAL)
        dut.uio_in.value = tx << RX_SERIAL  # loop TX serial into RX serial
        if bit(dut.uio_out, RX_EMPTY, default=1) == 0:
            got_data = True
            break

    assert got_data, "RX FIFO never became non-empty (byte never made it through)"

    # Pop the byte; sync_fifo is registered-read, so data is valid the next cycle
    dut.uio_in.value = 1 << RX_POP
    await RisingEdge(dut.clk)
    dut.uio_in.value = 0
    await RisingEdge(dut.clk)

    got = int(dut.uo_out.value)
    assert got == test_byte, f"loopback mismatch: sent {test_byte:#04x}, got {got:#04x}"
    dut._log.info(f"FIFO loopback OK: {test_byte:#04x} survived push->TX->RX->pop")
