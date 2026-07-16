#!/usr/bin/env python3

import argparse
import asyncio
import random
import sys
import time

# uio bits
RX_SERIAL = 0
TX_PUSH = 1  # also csr_sclk
RX_POP = 2
TX_SERIAL = 3
TX_FULL = 4
RX_EMPTY = 5
RX_ERROR = 6
CSR_MODE = 7

# csr registers
REG_CTRL = 0
REG_STATUS = 1
REG_SCRATCH = 2
REG_BAUD_LO = 3
REG_BAUD_HI = 4

CTRL_LOOPBACK = 0x01
CTRL_PARITY_EN = 0x02
CTRL_PARITY_ODD = 0x04

ST_TX_FULL = 0
ST_TX_EMPTY = 1
ST_RX_EMPTY = 2
ST_ERR_STICKY = 3
ST_OVF_STICKY = 4

FIFO_DEPTH = 16


def baud_plan(clk_hz, target_baud):
    # Multiple of 16
    div = max(16, round(clk_hz / target_baud / 16) * 16)
    if div > 0xFFFF:
        raise ValueError(f"divisor {div} exceeds 16 bits")
    return div, clk_hz / div


# One pin op per call
class Pins:
    async def drive_ui(self, byte):
        raise NotImplementedError

    async def drive_uio(self, bit, val):
        raise NotImplementedError

    async def read_uo(self):
        raise NotImplementedError

    async def read_uio(self, bit):
        raise NotImplementedError

    async def pause(self, ops=1):
        raise NotImplementedError


# Mirrors test/test.py
class Protocol:
    def __init__(self, pins):
        self.pins = pins

    async def _pulse(self, bit):
        await self.pins.drive_uio(bit, 1)
        await self.pins.pause()
        await self.pins.drive_uio(bit, 0)
        await self.pins.pause()

    async def push(self, byte):
        await self.pins.drive_ui(byte)
        await self.pins.pause()
        await self._pulse(TX_PUSH)

    async def pop(self):
        await self._pulse(RX_POP)
        return await self.pins.read_uo()

    async def rx_ready(self, timeout_ops=2000):
        for _ in range(timeout_ops):
            if await self.pins.read_uio(RX_EMPTY) == 0:
                return True
            await self.pins.pause(4)
        return False

    async def tx_full(self):
        return await self.pins.read_uio(TX_FULL)

    async def csr_frame(self, rw, addr, data):
        # 12 bits MSB first
        frame = ((rw & 1) << 11) | ((addr & 0x7) << 8) | (data & 0xFF)
        await self.pins.drive_uio(CSR_MODE, 1)
        await self.pins.pause(4)
        for i in range(11, -1, -1):
            await self.pins.drive_ui((frame >> i) & 1)
            await self.pins.pause()
            await self.pins.drive_uio(TX_PUSH, 1)  # csr_sclk
            await self.pins.pause(2)
            await self.pins.drive_uio(TX_PUSH, 0)
            await self.pins.pause(2)
        await self.pins.pause(10)  # sync and apb latency

    async def csr_write(self, addr, data):
        await self.csr_frame(1, addr, data)
        await self.pins.drive_uio(CSR_MODE, 0)
        await self.pins.drive_ui(0)
        await self.pins.pause(4)

    async def csr_read(self, addr):
        await self.csr_frame(0, addr, 0)
        val = await self.pins.read_uo()
        await self.pins.drive_uio(CSR_MODE, 0)
        await self.pins.drive_ui(0)
        await self.pins.pause(4)
        return val

    async def drain_rx(self):
        # Bounded drain
        for n in range(FIFO_DEPTH + 1):
            if await self.pins.read_uio(RX_EMPTY) == 1:
                return n
            await self.pop()
        return FIFO_DEPTH + 1


class HostSerial:
    async def send(self, data):
        raise NotImplementedError

    async def recv(self, n, timeout_s=2.0):
        raise NotImplementedError

    async def set_baud(self, baud):
        raise NotImplementedError


class StageFail(Exception):
    pass


def _expect(cond, msg):
    if not cond:
        raise StageFail(msg)


async def stage_alive(proto):
    await proto.csr_write(REG_CTRL, 0)  # clears sticky flags
    drained = await proto.drain_rx()
    for v in (0xA5, 0x5A, 0x00, 0xFF):
        await proto.csr_write(REG_SCRATCH, v)
        got = await proto.csr_read(REG_SCRATCH)
        _expect(got == v, f"SCRATCH wrote {v:#04x}, read {got:#04x}")
    status = await proto.csr_read(REG_STATUS)
    want = (1 << ST_TX_EMPTY) | (1 << ST_RX_EMPTY)
    _expect(status == want, f"STATUS {status:#04x}, expected {want:#04x}")
    return f"4 scratch patterns, status clean, {drained} stale rx drained"


async def stage_loopback(proto, n=16, seed=0xC0DE):
    rng = random.Random(seed)
    await proto.csr_write(REG_CTRL, CTRL_LOOPBACK)
    sent = 0
    for _ in range(n):
        b = rng.getrandbits(8)
        await proto.push(b)
        _expect(await proto.rx_ready(), f"loopback byte {b:#04x} never arrived")
        got = await proto.pop()
        _expect(got == b, f"loopback sent {b:#04x}, got {got:#04x}")
        sent += 1
    for ctrl in (CTRL_LOOPBACK | CTRL_PARITY_EN,
                 CTRL_LOOPBACK | CTRL_PARITY_EN | CTRL_PARITY_ODD):
        await proto.csr_write(REG_CTRL, ctrl)
        for b in (0x00, 0xFF, 0xA5):
            await proto.push(b)
            _expect(await proto.rx_ready(), f"parity byte {b:#04x} never arrived")
            got = await proto.pop()
            _expect(got == b, f"parity sent {b:#04x}, got {got:#04x}")
            sent += 1
    await proto.csr_write(REG_CTRL, 0)
    status = await proto.csr_read(REG_STATUS)
    _expect(not (status & (1 << ST_ERR_STICKY)), f"err_sticky set: {status:#04x}")
    return f"{sent} bytes echoed, none / even / odd parity"


async def stage_baud(proto, divisor):
    await proto.csr_write(REG_BAUD_LO, divisor & 0xFF)
    await proto.csr_write(REG_BAUD_HI, divisor >> 8)
    lo = await proto.csr_read(REG_BAUD_LO)
    hi = await proto.csr_read(REG_BAUD_HI)
    got = (hi << 8) | lo
    _expect(got == divisor, f"divisor wrote {divisor}, read {got}")
    return f"divisor {divisor} programmed and read back"


async def stage_link_rx(proto, ser, n=16, seed=0xF00D):
    # Host to chip
    rng = random.Random(seed)
    data = bytes(rng.getrandbits(8) for _ in range(n))
    for i, b in enumerate(data):
        await ser.send(bytes([b]))
        _expect(await proto.rx_ready(), f"link byte {i} ({b:#04x}) never arrived")
        got = await proto.pop()
        _expect(got == b, f"link byte {i}: sent {b:#04x}, got {got:#04x}")
    status = await proto.csr_read(REG_STATUS)
    _expect(not (status & (1 << ST_ERR_STICKY)), f"err_sticky set: {status:#04x}")
    return f"{n} bytes host to chip"


async def stage_link_tx(proto, ser, n=16, seed=0xBEEF):
    # Chip to host
    rng = random.Random(seed)
    data = bytes(rng.getrandbits(8) for _ in range(n))
    for i, b in enumerate(data):
        await proto.push(b)
        got = await ser.recv(1)
        _expect(len(got) == 1, f"link byte {i} ({b:#04x}) never reached host")
        _expect(got[0] == b, f"link byte {i}: pushed {b:#04x}, host got {got[0]:#04x}")
    return f"{n} bytes chip to host"


async def run_stages(proto, ser=None, divisor=None, link_bytes=16):
    results = []

    async def run(name, coro):
        try:
            detail = await coro
            results.append((name, True, detail))
            print(f"PASS {name}: {detail}")
        except StageFail as e:
            results.append((name, False, str(e)))
            print(f"FAIL {name}: {e}")
        return results[-1][1]

    ok = await run("alive", stage_alive(proto))
    if ok:
        ok = await run("loopback", stage_loopback(proto))
    if ok and divisor is not None:
        ok = await run("baud", stage_baud(proto, divisor))
    if ok and ser is not None:
        ok = await run("link_rx", stage_link_rx(proto, ser, link_bytes))
        if ok:
            await run("link_tx", stage_link_tx(proto, ser, link_bytes))
    return results


RP2040_USB_VID = 0x2E8A
FTDI_USB_VID = 0x0403


def find_port(vid, label):
    from serial.tools import list_ports
    hits = [p.device for p in list_ports.comports() if p.vid == vid]
    if len(hits) != 1:
        raise SystemExit(
            f"{label}: expected exactly one device with VID {vid:#06x}, "
            f"found {hits or 'none'} (pass the port explicitly)")
    return hits[0]


# Raw repl transport
class Rp2040Repl:
    def __init__(self, port):
        import serial
        self.ser = serial.Serial(port, 115200, timeout=3)
        self._enter_raw()

    def _enter_raw(self):
        self.ser.write(b"\r\x03\x03")  # Interrupt program
        time.sleep(0.3)
        self.ser.reset_input_buffer()
        self.ser.write(b"\r\x01")  # Raw repl
        buf = self.ser.read_until(b"raw REPL; CTRL-B to exit\r\n>")
        if not buf.endswith(b">"):
            raise RuntimeError(f"no raw REPL prompt, got {buf!r}")

    def exec(self, code):
        self.ser.write(code.encode() + b"\x04")
        ack = self.ser.read(2)
        if ack != b"OK":
            raise RuntimeError(f"raw REPL did not ack: {ack!r}")
        out = self.ser.read_until(b"\x04")[:-1]
        err = self.ser.read_until(b"\x04")[:-1]
        self.ser.read_until(b">")
        if err:
            raise RuntimeError(f"RP2040 error:\n{err.decode()}")
        return out.decode().strip()

    def close(self):
        self.ser.write(b"\r\x02")  # Exit raw repl
        self.ser.close()


# Demo board pins
class Rp2040Pins(Pins):
    def __init__(self, repl, project, clk_hz, drive_rx_idle):
        self.repl = repl
        oe = (1 << TX_PUSH) | (1 << RX_POP) | (1 << CSR_MODE)
        if drive_rx_idle:
            oe |= 1 << RX_SERIAL
        setup = f"""
from ttboard.demoboard import DemoBoard
from ttboard.mode import RPMode
import time
tt = DemoBoard.get()
tt.mode = RPMode.ASIC_RP_CONTROL
tt.shuttle.{project}.enable()
tt.clock_project_PWM({int(clk_hz)})
tt.uio_oe_pico.value = {oe:#04x}
tt.uio_in.value = {(1 << RX_SERIAL) if drive_rx_idle else 0:#04x}
tt.ui_in.value = 0
tt.reset_project(True)
time.sleep(0.05)
tt.reset_project(False)
print(tt.auto_clocking_freq)
"""
        freq = self.repl.exec(setup)
        print(f"demo board: {project} at {freq}")

    async def drive_ui(self, byte):
        self.repl.exec(f"tt.ui_in.value = {byte:#04x}")

    async def drive_uio(self, bit, val):
        self.repl.exec(f"tt.uio_in[{bit}] = {val}")

    async def read_uo(self):
        return int(self.repl.exec("print(int(tt.uo_out.value))"))

    async def read_uio(self, bit):
        return int(self.repl.exec(f"print(int(tt.uio_out[{bit}]))"))

    async def pause(self, ops=1):
        pass  # Repl delay suffices


class Ft232Serial(HostSerial):
    def __init__(self, port, baud):
        import serial
        self.ser = serial.Serial(port, baud, timeout=2)

    async def send(self, data):
        self.ser.write(data)
        self.ser.flush()

    async def recv(self, n, timeout_s=2.0):
        self.ser.timeout = timeout_s
        return self.ser.read(n)

    async def set_baud(self, baud):
        self.ser.baudrate = baud


# Echo through chip
async def echo_terminal(proto, ser):
    import termios
    import tty
    print("echo terminal, ctrl-C exits")
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    try:
        import select
        while True:
            r, _, _ = select.select([sys.stdin], [], [], 0.02)
            if r:
                ch = sys.stdin.read(1)
                await ser.send(ch.encode())
            if await proto.pins.read_uio(RX_EMPTY) == 0:
                b = await proto.pop()
                await proto.push(b)
            got = await ser.recv(1, timeout_s=0.02)
            if got:
                sys.stdout.write(got.decode(errors="replace"))
                sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print()


def main():
    ap = argparse.ArgumentParser(
        description="Staged bring-up for tt_um_drewbabel_uart")
    ap.add_argument("--board", help="RP2040 REPL port (auto-detect by VID)")
    ap.add_argument("--ft232", help="FT232 port, 'none' to skip link stages")
    ap.add_argument("--clock", type=float, default=12.5e6,
                    help="project clock in Hz (default 12.5e6)")
    ap.add_argument("--baud", type=float, default=115200,
                    help="target baud, snapped to a legal divisor")
    ap.add_argument("--bytes", type=int, default=16,
                    help="bytes per link direction")
    ap.add_argument("--project", default="tt_um_drewbabel_uart")
    ap.add_argument("--terminal", action="store_true",
                    help="drop into the echo terminal after the stages")
    args = ap.parse_args()

    divisor, actual = baud_plan(args.clock, args.baud)
    host_baud = round(actual)
    print(f"clock {args.clock/1e6:g} MHz, divisor {divisor}, "
          f"line rate {actual:.0f} baud")

    board = args.board or find_port(RP2040_USB_VID, "demo board")
    no_ft232 = args.ft232 == "none"
    ft232 = None if no_ft232 else (args.ft232 or find_port(FTDI_USB_VID, "FT232"))

    repl = Rp2040Repl(board)
    try:
        pins = Rp2040Pins(repl, args.project, args.clock, drive_rx_idle=no_ft232)
        proto = Protocol(pins)
        ser = Ft232Serial(ft232, host_baud) if ft232 else None
        results = asyncio.run(
            run_stages(proto, ser, divisor=divisor, link_bytes=args.bytes))
        failed = [n for n, ok, _ in results if not ok]
        if args.terminal and ser and not failed:
            asyncio.run(echo_terminal(proto, ser))
        print(f"{len(results) - len(failed)}/{len(results)} stages passed"
              + (f", failed: {', '.join(failed)}" if failed else ""))
        sys.exit(1 if failed else 0)
    finally:
        repl.close()


if __name__ == "__main__":
    main()
