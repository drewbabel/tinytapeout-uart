# SPDX-License-Identifier: Apache-2.0

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "demo"))

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

import harness
from harness import (
    HostSerial,
    Pins,
    Protocol,
    RX_SERIAL,
    TX_SERIAL,
    baud_plan,
    run_stages,
)

CLK_PERIOD_NS = 20
CLK_FREQ_HZ = 50_000_000


# Stands in for the RP2040
class SimPins(Pins):
    def __init__(self, dut):
        self.dut = dut
        self.uio = 1 << RX_SERIAL  # rx idles high

    async def drive_ui(self, byte):
        self.dut.ui_in.value = byte
        await ClockCycles(self.dut.clk, 1)

    async def drive_uio(self, bit, val):
        self.uio = (self.uio & ~(1 << bit)) | (val << bit)
        self.dut.uio_in.value = self.uio
        await ClockCycles(self.dut.clk, 1)

    async def read_uo(self):
        await ClockCycles(self.dut.clk, 1)
        return int(self.dut.uo_out.value)

    async def read_uio(self, bit):
        await ClockCycles(self.dut.clk, 1)
        v = str(self.dut.uio_out.value)[::-1][bit]
        return int(v) if v in "01" else 1

    async def pause(self, ops=1):
        await ClockCycles(self.dut.clk, 3 * ops)


# Stands in for the FT232
class SimSerial(HostSerial):
    def __init__(self, pins, cpb):
        self.pins = pins
        self.cpb = cpb

    async def _bit(self, level):
        await self.pins.drive_uio(RX_SERIAL, level)
        await ClockCycles(self.pins.dut.clk, self.cpb - 1)

    async def send(self, data):
        for byte in data:
            await self._bit(0)
            for i in range(8):
                await self._bit((byte >> i) & 1)
            await self._bit(1)

    async def recv(self, n, timeout_s=2.0):
        clk = self.pins.dut.clk
        out = bytearray()
        for _ in range(n):
            for _ in range(20 * self.cpb):
                if await self.pins.read_uio(TX_SERIAL) == 0:
                    break
            else:
                return bytes(out)
            await ClockCycles(clk, self.cpb // 2)
            byte = 0
            for i in range(8):
                await ClockCycles(clk, self.cpb)
                byte |= (await self.pins.read_uio(TX_SERIAL)) << i
            await ClockCycles(clk, self.cpb)  # Stop bit
            out.append(byte)
        return bytes(out)

    async def set_baud(self, baud):
        self.cpb = round(CLK_FREQ_HZ / baud)


async def start(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    pins = SimPins(dut)
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = pins.uio
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 20)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)
    return pins


@cocotb.test()
async def test_full_ladder(dut):
    pins = await start(dut)
    proto = Protocol(pins)
    divisor, actual = baud_plan(CLK_FREQ_HZ, 115_200)
    ser = SimSerial(pins, divisor)
    results = await run_stages(proto, ser, divisor=divisor, link_bytes=8)
    assert len(results) == 5, f"only {len(results)} stages ran: {results}"
    failed = [(n, d) for n, ok, d in results if not ok]
    assert not failed, f"stages failed: {failed}"


@cocotb.test()
async def test_ladder_without_ft232(dut):
    # No ft232 path
    pins = await start(dut)
    proto = Protocol(pins)
    divisor, _ = baud_plan(CLK_FREQ_HZ, 115_200)
    results = await run_stages(proto, ser=None, divisor=divisor)
    assert [n for n, _, _ in results] == ["alive", "loopback", "baud"]
    assert all(ok for _, ok, _ in results), f"failed: {results}"


@cocotb.test()
async def test_ladder_demo_board_plan(dut):
    # Demo board plan
    pins = await start(dut)
    proto = Protocol(pins)
    divisor, actual = baud_plan(12_500_000, 115_200)
    assert divisor == 112, divisor
    ser = SimSerial(pins, divisor)
    results = await run_stages(proto, ser, divisor=divisor, link_bytes=8)
    failed = [(n, d) for n, ok, d in results if not ok]
    assert not failed, f"stages failed: {failed}"


@cocotb.test()
async def test_echo_path(dut):
    # Echo terminal path
    pins = await start(dut)
    proto = Protocol(pins)
    divisor, _ = baud_plan(CLK_FREQ_HZ, 115_200)
    await proto.csr_write(harness.REG_BAUD_LO, divisor & 0xFF)
    await proto.csr_write(harness.REG_BAUD_HI, divisor >> 8)
    ser = SimSerial(pins, divisor)
    for ch in b"tt":
        await ser.send(bytes([ch]))
        assert await proto.rx_ready(), "echo byte never arrived"
        b = await proto.pop()
        assert b == ch, f"rx got {b:#04x}"
        await proto.push(b)
        got = await ser.recv(1)
        assert got == bytes([ch]), f"echo returned {got!r}"
