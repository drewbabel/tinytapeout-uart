# SPDX-License-Identifier: Apache-2.0
# Integration test: shift a serial frame in over the CSR pins and confirm it
# reaches apb_csr through the adapter (write CTRL/SCRATCH, read SCRATCH back)

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles

REG_CTRL = 0
REG_STATUS = 1
REG_SCRATCH = 2

# Hold each sclk phase this many clk cycles (>> 2-flop sync latency)
SCLK_HALF = 6


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    dut.csr_mode.value = 0
    dut.csr_sclk.value = 0
    dut.csr_mosi.value = 0
    dut.tx_full.value = 0
    dut.tx_empty.value = 0
    dut.rx_empty.value = 0
    dut.rx_error.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)


# Shift a 12-bit frame {rw, addr[2:0], data[7:0]} MSB-first over csr_mosi/csr_sclk
async def shift_frame(dut, rw, addr, data):
    frame = ((rw & 1) << 11) | ((addr & 0x7) << 8) | (data & 0xFF)
    dut.csr_mode.value = 1
    await ClockCycles(dut.clk, 2)
    for i in range(11, -1, -1):  # MSB first
        dut.csr_mosi.value = (frame >> i) & 1
        await ClockCycles(dut.clk, 2)  # Settle mosi before the edge
        dut.csr_sclk.value = 1
        await ClockCycles(dut.clk, SCLK_HALF)
        dut.csr_sclk.value = 0
        await ClockCycles(dut.clk, SCLK_HALF)
    # Let frame_valid + the APB transaction complete
    await ClockCycles(dut.clk, 8)


# Background monitor: latch rdata_out whenever read_valid pulses
async def _capture_reads(dut, box):
    while True:
        await RisingEdge(dut.clk)
        if int(dut.read_valid.value) == 1:
            box["val"] = int(dut.rdata_out.value)


# Shift a read frame and catch one-cycle read_valid pulse
async def read_frame(dut, addr):
    box = {"val": None}
    mon = cocotb.start_soon(_capture_reads(dut, box))
    frame = (0 << 11) | ((addr & 0x7) << 8)  # rw=0
    dut.csr_mode.value = 1
    await ClockCycles(dut.clk, 2)
    for i in range(11, -1, -1):
        dut.csr_mosi.value = (frame >> i) & 1
        await ClockCycles(dut.clk, 2)
        dut.csr_sclk.value = 1
        await ClockCycles(dut.clk, SCLK_HALF)
        dut.csr_sclk.value = 0
        await ClockCycles(dut.clk, SCLK_HALF)
    await ClockCycles(dut.clk, 8)
    mon.kill()
    return box["val"]


@cocotb.test()
async def test_serial_write_ctrl(dut):
    await reset(dut)
    await shift_frame(dut, rw=1, addr=REG_CTRL, data=0x01)
    assert dut.loopback_en.value == 1, "CTRL write over serial did not set loopback_en"


@cocotb.test()
async def test_serial_scratch_roundtrip(dut):
    await reset(dut)
    await shift_frame(dut, rw=1, addr=REG_SCRATCH, data=0xA5)
    got = await read_frame(dut, REG_SCRATCH)
    assert got is not None, "read_valid never pulsed"
    assert got == 0xA5, f"SCRATCH round-trip over serial: wrote 0xA5, read {got:#04x}"


@cocotb.test()
async def test_serial_status_read(dut):
    await reset(dut)
    dut.tx_full.value = 1
    dut.rx_empty.value = 1
    got = await read_frame(dut, REG_STATUS)
    assert got is not None, "read_valid never pulsed"
    exp = (1 << 2) | (1 << 0)  # rx_empty, tx_full
    assert got == exp, f"STATUS read over serial: got {got:#04x}, expected {exp:#04x}"
