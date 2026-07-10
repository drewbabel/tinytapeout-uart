# SPDX-License-Identifier: Apache-2.0
# Isolation test for apb_csr: drive the APB slave directly and check the
# register file (write/read SCRATCH, CTRL -> loopback_en, STATUS readback).

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

REG_CTRL = 0
REG_STATUS = 1
REG_SCRATCH = 2
REG_BAUD_LO = 3
REG_BAUD_HI = 4


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    dut.psel.value = 0
    dut.penable.value = 0
    dut.pwrite.value = 0
    dut.paddr.value = 0
    dut.pwdata.value = 0
    dut.tx_full.value = 0
    dut.tx_empty.value = 0
    dut.rx_empty.value = 0
    dut.rx_error.value = 0
    dut.rx_overflow.value = 0
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


# APB write: SETUP (penable=0) then ACCESS (penable=1), pready is always 1
async def apb_write(dut, addr, data):
    dut.psel.value = 1
    dut.penable.value = 0
    dut.pwrite.value = 1
    dut.paddr.value = addr
    dut.pwdata.value = data
    await RisingEdge(dut.clk)
    dut.penable.value = 1
    await RisingEdge(dut.clk)  # write lands on this edge
    dut.psel.value = 0
    dut.penable.value = 0
    dut.pwrite.value = 0


# APB read: prdata is combinational on paddr, sample in the ACCESS phase
async def apb_read(dut, addr):
    dut.psel.value = 1
    dut.penable.value = 0
    dut.pwrite.value = 0
    dut.paddr.value = addr
    await RisingEdge(dut.clk)
    dut.penable.value = 1
    await Timer_1(dut)  # let combinational prdata settle
    val = int(dut.prdata.value)
    await RisingEdge(dut.clk)
    dut.psel.value = 0
    dut.penable.value = 0
    return val


# small settle so prdata reflects the driven paddr before we sample
async def Timer_1(dut):
    from cocotb.triggers import Timer
    await Timer(1, unit="ns")


@cocotb.test()
async def test_reset(dut):
    await reset(dut)
    assert dut.loopback_en.value == 0, "loopback_en not 0 after reset"
    assert int(dut.pready.value) == 1, "pready should be tied high"
    assert await apb_read(dut, REG_CTRL) == 0, "CTRL not 0 after reset"
    assert await apb_read(dut, REG_SCRATCH) == 0, "SCRATCH not 0 after reset"


@cocotb.test()
async def test_scratch_roundtrip(dut):
    await reset(dut)
    for val in (0xA5, 0x00, 0xFF, 0x3C):
        await apb_write(dut, REG_SCRATCH, val)
        got = await apb_read(dut, REG_SCRATCH)
        assert got == val, f"SCRATCH round-trip: wrote {val:#04x}, read {got:#04x}"


@cocotb.test()
async def test_ctrl_loopback(dut):
    await reset(dut)
    await apb_write(dut, REG_CTRL, 0x01)
    await Timer_1(dut)  # settle combinational loopback_en
    assert dut.loopback_en.value == 1, "loopback_en not set by CTRL bit0"
    assert await apb_read(dut, REG_CTRL) == 0x01, "CTRL readback mismatch"
    await apb_write(dut, REG_CTRL, 0x00)
    await Timer_1(dut)
    assert dut.loopback_en.value == 0, "loopback_en not cleared"


@cocotb.test()
async def test_status_readback(dut):
    await reset(dut)
    # STATUS = {ovf_sticky, err_sticky, rx_empty, tx_empty, tx_full}
    dut.tx_full.value = 1
    dut.tx_empty.value = 0
    dut.rx_empty.value = 1
    dut.rx_error.value = 0
    got = await apb_read(dut, REG_STATUS)
    exp = (0 << 3) | (1 << 2) | (0 << 1) | (1 << 0)  # 0b0101 = 0x5
    assert got == exp, f"STATUS readback: got {got:#04x}, expected {exp:#04x}"


@cocotb.test()
async def test_write_is_readonly_status(dut):
    await reset(dut)
    # writing STATUS must not stick (no writable reg there)
    await apb_write(dut, REG_STATUS, 0xFF)
    dut.tx_full.value = 0
    dut.tx_empty.value = 0
    dut.rx_empty.value = 0
    dut.rx_error.value = 0
    got = await apb_read(dut, REG_STATUS)
    assert got == 0, f"STATUS should reflect inputs (0), got {got:#04x}"


@cocotb.test()
async def test_baud_roundtrip(dut):
    await reset(dut)
    await apb_write(dut, REG_BAUD_LO, 0xB2)
    await apb_write(dut, REG_BAUD_HI, 0x01)
    assert await apb_read(dut, REG_BAUD_LO) == 0xB2, "BAUD_LO readback"
    assert await apb_read(dut, REG_BAUD_HI) == 0x01, "BAUD_HI readback"
    await Timer_1(dut)
    assert int(dut.baud_div.value) == 0x01B2, f"baud_div = {int(dut.baud_div.value):#06x}"


@cocotb.test()
async def test_ctrl_parity_bits(dut):
    await reset(dut)
    await apb_write(dut, REG_CTRL, 0b110)  # parity_odd=1, parity_en=1
    await Timer_1(dut)
    assert dut.parity_en.value == 1, "parity_en not set by CTRL bit1"
    assert dut.parity_odd.value == 1, "parity_odd not set by CTRL bit2"
    await apb_write(dut, REG_CTRL, 0b000)
    await Timer_1(dut)
    assert dut.parity_en.value == 0, "parity_en not cleared"
    assert dut.parity_odd.value == 0, "parity_odd not cleared"
