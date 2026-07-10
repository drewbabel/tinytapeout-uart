# SPDX-License-Identifier: Apache-2.0
# Parity and runtime baud through loopback and direct frames

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles, Timer

CLK_NS = 20
CLKS_PER_BIT = 434  # 50 MHz / 115200, default baud


def even_parity(b):
    return bin(b).count("1") % 2


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_NS, unit="ns").start())
    dut.parity_en.value = 0
    dut.parity_odd.value = 0
    dut.baud_div.value = 0
    dut.tx_data.value = 0
    dut.tx_valid.value = 0
    dut.rx_serial.value = 1
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)


async def _loopback(dut):
    while True:
        await RisingEdge(dut.clk)
        dut.rx_serial.value = int(dut.tx_serial.value)


# Send one byte through the loopback
async def send_recv(dut, byte, max_cycles=12000):
    while int(dut.tx_ready.value) != 1:
        await RisingEdge(dut.clk)
    dut.tx_data.value = byte
    dut.tx_valid.value = 1
    await RisingEdge(dut.clk)
    dut.tx_valid.value = 0
    for _ in range(max_cycles):
        await RisingEdge(dut.clk)
        if int(dut.rx_valid.value) == 1:
            return int(dut.rx_data.value), 0
        if int(dut.rx_error.value) == 1:
            return None, 1
    return None, -1


@cocotb.test()
async def test_no_parity_loopback(dut):
    await reset(dut)
    mon = cocotb.start_soon(_loopback(dut))
    for b in (0x00, 0xA5, 0xFF, 0x5A):
        data, err = await send_recv(dut, b)
        assert err == 0 and data == b, f"8N1 loopback: sent {b:#04x}, got {data}, err {err}"
    mon.kill()


@cocotb.test()
async def test_parity_even_loopback(dut):
    await reset(dut)
    dut.parity_en.value = 1
    dut.parity_odd.value = 0
    mon = cocotb.start_soon(_loopback(dut))
    for b in (0xA5, 0x3C, 0xFF, 0x01):
        data, err = await send_recv(dut, b)
        assert err == 0 and data == b, f"even-parity loopback: sent {b:#04x}, got {data}, err {err}"
    mon.kill()


@cocotb.test()
async def test_parity_odd_loopback(dut):
    await reset(dut)
    dut.parity_en.value = 1
    dut.parity_odd.value = 1
    mon = cocotb.start_soon(_loopback(dut))
    for b in (0xA5, 0x00, 0x7E):
        data, err = await send_recv(dut, b)
        assert err == 0 and data == b, f"odd-parity loopback: sent {b:#04x}, got {data}, err {err}"
    mon.kill()


@cocotb.test()
async def test_baud_runtime_loopback(dut):
    await reset(dut)
    dut.baud_div.value = 868  # half speed (2x the default divisor)
    mon = cocotb.start_soon(_loopback(dut))
    for b in (0xA5, 0x33):
        data, err = await send_recv(dut, b, max_cycles=24000)
        assert err == 0 and data == b, f"runtime-baud loopback: sent {b:#04x}, got {data}, err {err}"
    mon.kill()


# Drive one frame with a chosen parity bit
async def drive_frame(dut, data, par_bit):
    async def bit(level):
        dut.rx_serial.value = level
        await ClockCycles(dut.clk, CLKS_PER_BIT)

    await bit(0)  # start
    for i in range(8):
        await bit((data >> i) & 1)
    await bit(par_bit)
    await bit(1)  # stop
    await bit(1)  # idle


@cocotb.test()
async def test_parity_error_detected(dut):
    await reset(dut)
    dut.parity_en.value = 1
    dut.parity_odd.value = 0  # even

    saw_error = [False]

    async def watch():
        while True:
            await RisingEdge(dut.clk)
            if int(dut.rx_error.value) == 1:
                saw_error[0] = True

    mon = cocotb.start_soon(watch())
    # Drive the wrong parity bit
    await drive_frame(dut, 0xA5, par_bit=1 - even_parity(0xA5))
    mon.kill()
    assert saw_error[0], "rx_error not raised on bad parity bit"
