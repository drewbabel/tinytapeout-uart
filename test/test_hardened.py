# SPDX-License-Identifier: Apache-2.0

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

# Design constants (match src/project.sv)
CLK_PERIOD_NS = 20
BAUD_RATE = 115_200
CLK_FREQ_HZ = 50_000_000
BAUD_DIV = (CLK_FREQ_HZ + BAUD_RATE // 2) // BAUD_RATE

# Pin map (see src/project.sv)
RX_SERIAL = 0
TX_PUSH = 1
RX_POP = 2
TX_SERIAL = 3
TX_FULL = 4
RX_EMPTY = 5
RX_ERROR = 6

IDLE = 1 << RX_SERIAL  # RX line idles HIGH


def bit(sig, i, default=1):
    s = str(sig.value)[::-1]  # LSB-first
    if i >= len(s):
        return default
    c = s[i]
    return int(c) if c in "01" else default


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = IDLE
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 20)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)


# Push one byte into the TX FIFO
async def push_tx(dut, byte):
    dut.ui_in.value = byte
    dut.uio_in.value = IDLE | (1 << TX_PUSH)
    await RisingEdge(dut.clk)
    dut.uio_in.value = IDLE


# Loop tx_serial into rx_serial until the RX FIFO has data
async def loopback_until_rx(dut, max_cycles=8000):
    for _ in range(max_cycles):
        await RisingEdge(dut.clk)
        tx = bit(dut.uio_out, TX_SERIAL)
        dut.uio_in.value = tx << RX_SERIAL
        if bit(dut.uio_out, RX_EMPTY, default=1) == 0:
            return True
    return False


# Pop one byte (registered read: valid the next cycle)
async def pop_rx(dut):
    dut.uio_in.value = IDLE | (1 << RX_POP)
    await RisingEdge(dut.clk)
    dut.uio_in.value = IDLE
    await RisingEdge(dut.clk)
    return int(dut.uo_out.value)


@cocotb.test()
async def test_random_loopback(dut):
    await reset(dut)
    random.seed(0xC0DE)

    for i in range(100):
        data = random.getrandbits(8)
        await push_tx(dut, data)
        assert await loopback_until_rx(dut), f"byte {i} ({data:#04x}) never arrived"
        got = await pop_rx(dut)
        assert got == data, f"byte {i}: sent {data:#04x}, got {got:#04x}"
        assert bit(dut.uio_out, RX_ERROR, default=0) == 0, f"byte {i}: spurious rx_error"


# Drive one frame onto rx_serial, LSB first; return whether rx_error pulsed
async def drive_frame(dut, byte, good_stop=True):
    saw_error = [False]

    async def drive_bit(level):
        dut.uio_in.value = level << RX_SERIAL
        for _ in range(BAUD_DIV):
            await RisingEdge(dut.clk)
            if bit(dut.uio_out, RX_ERROR, default=0) == 1:
                saw_error[0] = True

    await drive_bit(0)                       # START
    for i in range(8):
        await drive_bit((byte >> i) & 1)     # data
    await drive_bit(1 if good_stop else 0)   # STOP
    await drive_bit(1)                       # idle
    return saw_error[0]


@cocotb.test()
async def test_framing_error(dut):
    await reset(dut)
    assert await drive_frame(dut, 0xA5, good_stop=False), "rx_error not raised on bad stop bit"
    assert bit(dut.uio_out, RX_EMPTY, default=1) == 1, "malformed frame delivered a byte"
