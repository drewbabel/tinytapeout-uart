# SPDX-License-Identifier: Apache-2.0

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

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


# Pop one byte
async def pop_rx(dut):
    dut.uio_in.value = IDLE | (1 << RX_POP)
    await ClockCycles(dut.clk, 2)
    dut.uio_in.value = IDLE
    await ClockCycles(dut.clk, 6)
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


# Drive one frame onto rx_serial, LSB first, then return whether rx_error pulsed
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


# RX bit period at reset default (16 oversamples * 27 clk)
RX_BIT_CLKS = 432
BAUD_FAST = (RX_BIT_CLKS * 96) // 100   # TX 4% fast
BAUD_SLOW = (RX_BIT_CLKS * 104) // 100  # TX 4% slow


# Drive one 8N1 frame at an arbitrary bit period, watching rx_error
async def drive_frame_cpb(dut, byte, cpb, good_stop=True):
    saw_error = [False]

    async def drive_bit(level):
        dut.uio_in.value = level << RX_SERIAL
        for _ in range(cpb):
            await RisingEdge(dut.clk)
            if bit(dut.uio_out, RX_ERROR, default=0) == 1:
                saw_error[0] = True

    await drive_bit(0)                       # Start bit
    for i in range(8):
        await drive_bit((byte >> i) & 1)     # Data bits, LSB first
    await drive_bit(1 if good_stop else 0)   # Stop bit
    dut.uio_in.value = IDLE
    return saw_error[0]


# Drive a clean frame, then check it landed intact in the RX FIFO
async def expect_byte(dut, byte, cpb):
    err = await drive_frame_cpb(dut, byte, cpb)
    await ClockCycles(dut.clk, 5)
    assert bit(dut.uio_out, RX_EMPTY, default=1) == 0, \
        f"byte {byte:#04x} @{cpb} clk/bit never landed"
    got = await pop_rx(dut)
    assert got == byte, f"@{cpb} clk/bit: sent {byte:#04x}, got {got:#04x}"
    assert not err, f"byte {byte:#04x} @{cpb} clk/bit: spurious rx_error"


@cocotb.test()
async def test_all_values_nominal(dut):
    await reset(dut)
    for data in (0x00, 0xFF, 0xA5, 0x5A, 0x0F, 0xF0, 0x81, 0x7E):
        await expect_byte(dut, data, RX_BIT_CLKS)


@cocotb.test()
async def test_baud_tolerance(dut):
    # +/-4% baud mismatch must still decode
    await reset(dut)
    for cpb in (BAUD_FAST, BAUD_SLOW):
        for data in (0x00, 0xFF, 0xA5, 0x5A):
            await expect_byte(dut, data, cpb)


@cocotb.test()
async def test_start_glitch_reject(dut):
    # A narrow low glitch must not launch a frame (line must hold low to mid-start)
    await reset(dut)
    dut.uio_in.value = 0 << RX_SERIAL      # Narrow low glitch
    await ClockCycles(dut.clk, 3)
    dut.uio_in.value = IDLE
    await ClockCycles(dut.clk, RX_BIT_CLKS * 2)
    assert bit(dut.uio_out, RX_EMPTY, default=1) == 1, "glitch spawned a phantom byte"
    assert bit(dut.uio_out, RX_ERROR, default=0) == 0, "glitch raised rx_error"


@cocotb.test()
async def test_back_to_back(dut):
    # Two frames minimally spaced: RX must re-arm in time for the next start edge
    await reset(dut)
    for data in (0x3C, 0xC3):
        await expect_byte(dut, data, RX_BIT_CLKS)


# CSR path through the tile pins

CSR_MODE = 7
CSR_SCLK = 1

REG_CTRL = 0
REG_STATUS = 1
REG_SCRATCH = 2
REG_BAUD_LO = 3
REG_BAUD_HI = 4

# STATUS bits
ST_TX_FULL = 0
ST_TX_EMPTY = 1
ST_RX_EMPTY = 2
ST_ERR_STICKY = 3
ST_OVF_STICKY = 4


# Shift a 12-bit frame MSB-first, csr_mode left high
async def csr_frame(dut, rw, addr, data=0):
    frame = ((rw & 1) << 11) | ((addr & 0x7) << 8) | (data & 0xFF)
    dut.uio_in.value = IDLE | (1 << CSR_MODE)
    await ClockCycles(dut.clk, 4)
    for i in range(11, -1, -1):
        dut.ui_in.value = (frame >> i) & 1
        await ClockCycles(dut.clk, 3)
        dut.uio_in.value = IDLE | (1 << CSR_MODE) | (1 << CSR_SCLK)
        await ClockCycles(dut.clk, 6)
        dut.uio_in.value = IDLE | (1 << CSR_MODE)
        await ClockCycles(dut.clk, 6)
    await ClockCycles(dut.clk, 10)  # sync latency + APB SETUP/ACCESS


async def csr_write(dut, addr, data):
    await csr_frame(dut, 1, addr, data)
    dut.uio_in.value = IDLE
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 5)


# Read a register over the pins
async def csr_read(dut, addr):
    await csr_frame(dut, 0, addr)
    val = int(dut.uo_out.value)
    dut.uio_in.value = IDLE
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 5)
    return val


# Wait for a byte in the RX FIFO
async def wait_rx_ready(dut, max_cycles=20000):
    for _ in range(max_cycles):
        await RisingEdge(dut.clk)
        if bit(dut.uio_out, RX_EMPTY, default=1) == 0:
            return True
    return False


@cocotb.test()
async def test_csr_scratch_and_status_via_pins(dut):
    await reset(dut)
    await csr_write(dut, REG_SCRATCH, 0xA5)
    got = await csr_read(dut, REG_SCRATCH)
    assert got == 0xA5, f"SCRATCH via pins: wrote 0xA5, read {got:#04x}"
    status = await csr_read(dut, REG_STATUS)
    exp = (1 << ST_TX_EMPTY) | (1 << ST_RX_EMPTY)
    assert status == exp, f"STATUS via pins: got {status:#04x}, expected {exp:#04x}"


@cocotb.test()
async def test_csr_loopback_via_pins(dut):
    await reset(dut)
    await csr_write(dut, REG_CTRL, 0x01)  # loopback_en
    for data in (0x5A, 0x81):
        await push_tx(dut, data)
        assert await wait_rx_ready(dut), f"loopback byte {data:#04x} never arrived"
        got = await pop_rx(dut)
        assert got == data, f"CSR loopback: sent {data:#04x}, got {got:#04x}"


@cocotb.test()
async def test_csr_parity_via_pins(dut):
    await reset(dut)
    # loopback + parity_en + parity_odd
    await csr_write(dut, REG_CTRL, 0b111)
    for data in (0xA5, 0x00, 0xFF):
        await push_tx(dut, data)
        assert await wait_rx_ready(dut), f"parity byte {data:#04x} never arrived"
        got = await pop_rx(dut)
        assert got == data, f"CSR parity loopback: sent {data:#04x}, got {got:#04x}"
        assert bit(dut.uio_out, RX_ERROR, default=0) == 0, "spurious rx_error"


@cocotb.test()
async def test_csr_runtime_baud_via_pins(dut):
    await reset(dut)
    await csr_write(dut, REG_BAUD_LO, 868 & 0xFF)
    await csr_write(dut, REG_BAUD_HI, 868 >> 8)
    await csr_write(dut, REG_CTRL, 0x01)  # loopback at half speed
    await push_tx(dut, 0x3C)
    assert await wait_rx_ready(dut, max_cycles=40000), "half-speed byte never arrived"
    got = await pop_rx(dut)
    assert got == 0x3C, f"runtime baud via pins: sent 0x3c, got {got:#04x}"


@cocotb.test()
async def test_push_held_high_is_one_push(dut):
    # Held-high push must enqueue exactly one byte
    await reset(dut)
    await csr_write(dut, REG_CTRL, 0x01)  # loopback
    dut.ui_in.value = 0x77
    dut.uio_in.value = IDLE | (1 << TX_PUSH)
    await ClockCycles(dut.clk, 200)
    dut.uio_in.value = IDLE
    assert await wait_rx_ready(dut), "held-push byte never arrived"
    got = await pop_rx(dut)
    assert got == 0x77, f"held push: got {got:#04x}"
    # No second byte
    await ClockCycles(dut.clk, 6000)
    assert bit(dut.uio_out, RX_EMPTY, default=1) == 1, "held push enqueued more than one byte"


@cocotb.test()
async def test_pop_held_high_is_one_pop(dut):
    await reset(dut)
    await csr_write(dut, REG_CTRL, 0x01)  # loopback
    for data in (0x11, 0x22):
        await push_tx(dut, data)
        await ClockCycles(dut.clk, 20)
    await wait_rx_ready(dut)
    await ClockCycles(dut.clk, 10000)  # both bytes land in the RX FIFO
    # Held-high pop must dequeue exactly one byte
    dut.uio_in.value = IDLE | (1 << RX_POP)
    await ClockCycles(dut.clk, 100)
    dut.uio_in.value = IDLE
    await ClockCycles(dut.clk, 6)
    assert int(dut.uo_out.value) == 0x11, "held pop returned wrong byte"
    assert bit(dut.uio_out, RX_EMPTY, default=1) == 0, "held pop drained more than one byte"
    got = await pop_rx(dut)
    assert got == 0x22, f"second byte: got {got:#04x}"


@cocotb.test()
async def test_tx_full_backpressure_via_pins(dut):
    await reset(dut)
    await csr_write(dut, REG_CTRL, 0x01)  # loopback
    saw_full = False
    for i in range(18):
        await push_tx(dut, i)
        await ClockCycles(dut.clk, 6)
        if bit(dut.uio_out, TX_FULL, default=0) == 1:
            saw_full = True
    assert saw_full, "tx_full never asserted after 18 pushes into a 16-deep FIFO"
    received = []
    while True:
        if not await wait_rx_ready(dut, max_cycles=8000):
            break
        received.append(await pop_rx(dut))
    assert len(received) >= 16, f"only {len(received)} bytes came back"
    assert received == list(range(len(received))), f"order corrupted: {received}"


@cocotb.test()
async def test_pop_on_empty_is_harmless(dut):
    await reset(dut)
    assert bit(dut.uio_out, RX_EMPTY, default=1) == 1
    for _ in range(3):
        dut.uio_in.value = IDLE | (1 << RX_POP)
        await ClockCycles(dut.clk, 4)
        dut.uio_in.value = IDLE
        await ClockCycles(dut.clk, 4)
    assert bit(dut.uio_out, RX_EMPTY, default=1) == 1, "pop on empty changed rx_empty"
    # Tile still works afterwards
    await csr_write(dut, REG_CTRL, 0x01)
    await push_tx(dut, 0xC3)
    assert await wait_rx_ready(dut), "byte after empty-pops never arrived"
    assert await pop_rx(dut) == 0xC3


@cocotb.test()
async def test_reset_midframe_recovers(dut):
    await reset(dut)
    await csr_write(dut, REG_CTRL, 0x01)  # loopback
    await push_tx(dut, 0xE7)
    await ClockCycles(dut.clk, 1000)  # mid-frame
    dut.rst_n.value = 0
    dut.uio_in.value = IDLE
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 20)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)
    # Re-enable loopback after reset
    await csr_write(dut, REG_CTRL, 0x01)
    await push_tx(dut, 0x99)
    assert await wait_rx_ready(dut), "byte after mid-frame reset never arrived"
    got = await pop_rx(dut)
    assert got == 0x99, f"after reset: got {got:#04x}"


@cocotb.test()
async def test_sticky_error_and_clear_via_pins(dut):
    await reset(dut)
    # Bad stop bit latches err_sticky
    await drive_frame(dut, 0x0F, good_stop=False)
    await ClockCycles(dut.clk, 10)
    status = await csr_read(dut, REG_STATUS)
    assert status & (1 << ST_ERR_STICKY), f"err_sticky not set: {status:#04x}"
    await csr_write(dut, REG_CTRL, 0x00)
    status = await csr_read(dut, REG_STATUS)
    assert not (status & (1 << ST_ERR_STICKY)), f"err_sticky not cleared: {status:#04x}"


@cocotb.test()
async def test_sticky_overflow_via_pins(dut):
    await reset(dut)
    # Fast divisor so 17 frames fit in sim time
    await csr_write(dut, REG_BAUD_LO, 64)
    for i in range(17):
        await drive_frame_cpb(dut, i & 0xFF, 64)
    dut.uio_in.value = IDLE
    await ClockCycles(dut.clk, 20)
    status = await csr_read(dut, REG_STATUS)
    assert status & (1 << ST_OVF_STICKY), f"ovf_sticky not set: {status:#04x}"
    assert not (status & (1 << ST_ERR_STICKY)), f"spurious err_sticky: {status:#04x}"
    # Drain and check all 16 retained bytes in order
    for i in range(16):
        assert bit(dut.uio_out, RX_EMPTY, default=1) == 0, f"FIFO ran dry at byte {i}"
        got = await pop_rx(dut)
        assert got == i, f"post-overflow drain: slot {i} held {got:#04x}"
    assert bit(dut.uio_out, RX_EMPTY, default=1) == 1, "more than 16 bytes retained"


# Drive one frame with an explicit parity bit
async def drive_frame_par(dut, byte, par_bit, cpb=RX_BIT_CLKS):
    async def drive_bit(level):
        dut.uio_in.value = level << RX_SERIAL
        for _ in range(cpb):
            await RisingEdge(dut.clk)

    await drive_bit(0)                    # start
    for i in range(8):
        await drive_bit((byte >> i) & 1)  # data, LSB first
    await drive_bit(par_bit)              # parity
    await drive_bit(1)                    # stop
    dut.uio_in.value = IDLE


@cocotb.test()
async def test_parity_error_sticky_via_pins(dut):
    # Bad parity latches err_sticky, survives a non-CTRL write
    await reset(dut)
    await csr_write(dut, REG_CTRL, 0b010)  # parity_en, even
    good_par = bin(0xA5).count("1") % 2
    await drive_frame_par(dut, 0xA5, 1 - good_par)
    await ClockCycles(dut.clk, 10)
    assert bit(dut.uio_out, RX_EMPTY, default=1) == 1, "bad-parity byte was delivered"
    status = await csr_read(dut, REG_STATUS)
    assert status & (1 << ST_ERR_STICKY), f"err_sticky not set: {status:#04x}"
    await csr_write(dut, REG_SCRATCH, 0x77)  # unrelated write must not clear it
    status = await csr_read(dut, REG_STATUS)
    assert status & (1 << ST_ERR_STICKY), f"SCRATCH write cleared err_sticky: {status:#04x}"
    await csr_write(dut, REG_CTRL, 0b010)
    status = await csr_read(dut, REG_STATUS)
    assert not (status & (1 << ST_ERR_STICKY)), f"err_sticky not cleared: {status:#04x}"
    # Good parity still gets through
    await drive_frame_par(dut, 0x3C, bin(0x3C).count("1") % 2)
    await ClockCycles(dut.clk, 10)
    assert bit(dut.uio_out, RX_EMPTY, default=1) == 0, "good-parity byte never arrived"
    assert await pop_rx(dut) == 0x3C


@cocotb.test()
async def test_midframe_baud_write_via_pins(dut):
    # In-flight byte runs at the old divisor, the queued byte at the new
    await reset(dut)
    await csr_write(dut, REG_CTRL, 0x01)  # loopback at default divisor
    await push_tx(dut, 0xA5)
    await ClockCycles(dut.clk, 8)  # release the strobe between pushes
    await push_tx(dut, 0x3C)
    await ClockCycles(dut.clk, 500)  # byte one is mid-frame
    await csr_write(dut, REG_BAUD_LO, 64)  # divisor 434 -> 64
    assert await wait_rx_ready(dut), "in-flight byte never arrived"
    assert await pop_rx(dut) == 0xA5, "mid-frame BAUD write corrupted the in-flight byte"
    assert await wait_rx_ready(dut), "queued byte never arrived at the new divisor"
    assert await pop_rx(dut) == 0x3C, "queued byte corrupted after divisor change"
    status = await csr_read(dut, REG_STATUS)
    assert not (status & (1 << ST_ERR_STICKY)), f"reconfig raised an error: {status:#04x}"


@cocotb.test()
async def test_min_divisor_via_pins(dut):
    # Minimum divisor through the pins
    await reset(dut)
    await csr_write(dut, REG_BAUD_LO, 16)
    await csr_write(dut, REG_CTRL, 0x01)  # loopback
    for data in (0xA5, 0x5A):
        await push_tx(dut, data)
        assert await wait_rx_ready(dut), f"divisor-16 byte {data:#04x} never arrived"
        got = await pop_rx(dut)
        assert got == data, f"divisor 16: sent {data:#04x}, got {got:#04x}"


@cocotb.test()
async def test_push_data_hold_contract(dut):
    # ui_in may change a few clocks after the push release
    await reset(dut)
    await csr_write(dut, REG_CTRL, 0x01)  # loopback
    dut.ui_in.value = 0x5A
    dut.uio_in.value = IDLE | (1 << TX_PUSH)
    await ClockCycles(dut.clk, 3)
    dut.uio_in.value = IDLE
    await ClockCycles(dut.clk, 3)
    dut.ui_in.value = 0xFF  # too late to matter
    assert await wait_rx_ready(dut), "held-data byte never arrived"
    got = await pop_rx(dut)
    assert got == 0x5A, f"capture raced the release: got {got:#04x}"


@cocotb.test()
async def test_pop_gated_in_csr_mode(dut):
    await reset(dut)
    await csr_write(dut, REG_CTRL, 0x01)  # loopback
    await push_tx(dut, 0xC3)
    assert await wait_rx_ready(dut), "byte never arrived"
    dut.uio_in.value = IDLE | (1 << CSR_MODE)
    await ClockCycles(dut.clk, 6)
    for _ in range(2):
        dut.uio_in.value = IDLE | (1 << CSR_MODE) | (1 << RX_POP)
        await ClockCycles(dut.clk, 4)
        dut.uio_in.value = IDLE | (1 << CSR_MODE)
        await ClockCycles(dut.clk, 4)
    dut.uio_in.value = IDLE
    await ClockCycles(dut.clk, 6)
    assert bit(dut.uio_out, RX_EMPTY, default=1) == 0, "pop fired during CSR mode"
    assert await pop_rx(dut) == 0xC3, "byte lost across CSR-mode pop pulses"


@cocotb.test()
async def test_csr_ctrl_baud_readback_via_pins(dut):
    # The remaining prdata arms
    await reset(dut)
    await csr_write(dut, REG_CTRL, 0x06)  # parity_en + parity_odd, no traffic
    got = await csr_read(dut, REG_CTRL)
    assert got == 0x06, f"CTRL readback via pins: {got:#04x}"
    await csr_write(dut, REG_BAUD_LO, 0xB2)
    await csr_write(dut, REG_BAUD_HI, 0x01)
    got = await csr_read(dut, REG_BAUD_LO)
    assert got == 0xB2, f"BAUD_LO readback via pins: {got:#04x}"
    got = await csr_read(dut, REG_BAUD_HI)
    assert got == 0x01, f"BAUD_HI readback via pins: {got:#04x}"


@cocotb.test()
async def test_unmapped_addrs_via_pins(dut):
    await reset(dut)
    await csr_write(dut, REG_SCRATCH, 0x3C)
    await csr_write(dut, 7, 0x5A)
    for addr in (5, 6, 7):
        got = await csr_read(dut, addr)
        assert got == 0, f"unmapped addr {addr} read {got:#04x}"
    got = await csr_read(dut, REG_SCRATCH)
    assert got == 0x3C, f"unmapped write disturbed SCRATCH: {got:#04x}"


@cocotb.test()
async def test_csr_mode_exit_no_spurious_push(dut):
    # Mode exit with sclk high must not push a byte
    await reset(dut)
    frame = (1 << 11) | (REG_SCRATCH << 8) | 0x42  # harmless SCRATCH write
    dut.uio_in.value = IDLE | (1 << CSR_MODE)
    await ClockCycles(dut.clk, 4)
    for i in range(11, -1, -1):
        dut.ui_in.value = (frame >> i) & 1
        await ClockCycles(dut.clk, 3)
        dut.uio_in.value = IDLE | (1 << CSR_MODE) | (1 << CSR_SCLK)
        await ClockCycles(dut.clk, 6)
        if i > 0:
            dut.uio_in.value = IDLE | (1 << CSR_MODE)
            await ClockCycles(dut.clk, 6)
    await ClockCycles(dut.clk, 10)
    # Exit with the shared pin high
    dut.uio_in.value = IDLE | (1 << TX_PUSH)
    await ClockCycles(dut.clk, 20)
    dut.uio_in.value = IDLE
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 20)
    status = await csr_read(dut, REG_STATUS)
    assert status & (1 << ST_TX_EMPTY), \
        f"mode exit with sclk high pushed a spurious byte: STATUS={status:#04x}"
    got = await csr_read(dut, REG_SCRATCH)
    assert got == 0x42, f"SCRATCH write before mode exit lost: {got:#04x}"
