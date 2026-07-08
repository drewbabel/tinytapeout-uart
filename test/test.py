# SPDX-License-Identifier: Apache-2.0
#
# SMOKE TEST ONLY. This proves the tt_um pin-wrapper is wired correctly:
# it transmits a byte, loops TX->RX externally, and checks the byte comes back.
# It is NOT the credibly-engineered verification suite (TT.2) -- replace/expand
# this with a cocotb reference-model + randomized/constrained self-checking test
# (steal the discipline from drewbabel/uart's test suite).

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

# Pin map (see src/project.v)
RX_SERIAL = 0  # uio_in[0]
TX_VALID = 1   # uio_in[1]
TX_SERIAL = 2  # uio_out[2]
TX_READY = 3   # uio_out[3]
RX_VALID = 4   # uio_out[4]
RX_ERROR = 5   # uio_out[5]


def bit(sig, i):
    return (int(sig.value) >> i) & 1


@cocotb.test()
async def test_loopback(dut):
    dut._log.info("Start: TX->RX loopback smoke test")

    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())  # 50 MHz

    # Reset
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    test_byte = 0xA5

    # Present the byte and pulse tx_valid for one accepted handshake
    dut.ui_in.value = test_byte
    dut.uio_in.value = 1 << TX_VALID
    await RisingEdge(dut.clk)
    dut.uio_in.value = 0  # drop tx_valid; rx_serial idles high via the loop below

    # Drive the loopback (TX serial -> RX serial) and watch for rx_valid.
    # Idle line is high; the mirror below carries the start bit through framing.
    got = None
    for _ in range(6000):
        await RisingEdge(dut.clk)
        tx = bit(dut.uio_out, TX_SERIAL)
        dut.uio_in.value = tx << RX_SERIAL  # loop TX line into RX line
        if bit(dut.uio_out, RX_VALID):
            got = int(dut.uo_out.value)
            break

    assert got is not None, "rx_valid never asserted -- byte never received"
    assert got == test_byte, f"loopback mismatch: sent {test_byte:#04x}, got {got:#04x}"
    assert bit(dut.uio_out, RX_ERROR) == 0, "unexpected framing error"
    dut._log.info(f"Loopback OK: {test_byte:#04x} received")
