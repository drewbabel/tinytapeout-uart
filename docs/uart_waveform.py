#!/usr/bin/env python3
# Renders uart_waveform.svg from uart_wave.csv (regen: uart_wave_tb.sv)
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SIG, GREY = "#08306b", "#dfe6ee"
lane_h, gap = 0.72, 0.55
pitch = lane_h + gap

rows = list(csv.DictReader(open("uart_wave.csv")))
N = len(rows)
tx = [int(r["tx_serial"]) for r in rows]
empty = [int(r["rx_empty"]) for r in rows]
err = [int(r["rx_error"]) for r in rows]
data = [int(r["uo_out"]) for r in rows]

lanes = [("tx_serial", tx, "bit"), ("rx_empty", empty, "bit"),
         ("rx_error", err, "bit"), ("uo_out", data, "bus")]
nlanes = len(lanes)

fig, ax = plt.subplots(figsize=(13, 0.62 * nlanes + 1.4))
base_of = lambda k: (nlanes - 1 - k) * pitch

for k, (name, vals, kind) in enumerate(lanes):
    base = base_of(k)
    if kind == "bit":
        ax.axhline(base, color=GREY, lw=0.8, zorder=0)
        seg = vals + [vals[-1]]
        ax.step(range(N + 1), [base + max(v, 0) * lane_h for v in seg],
                where="post", color=SIG, lw=1.8, zorder=3)
    else:
        top, bot = base + lane_h, base
        s = 0
        for i in range(1, N + 1):
            if i == N or vals[i] != vals[i - 1]:
                v = vals[s]
                ax.plot([s, i], [top, top], color=SIG, lw=1.7, zorder=3)
                ax.plot([s, i], [bot, bot], color=SIG, lw=1.7, zorder=3)
                ax.plot([s, s], [bot, top], color=SIG, lw=1.2, zorder=3)
                ax.plot([i, i], [bot, top], color=SIG, lw=1.2, zorder=3)
                ax.text((s + i) / 2, base + lane_h / 2, f"0x{v & 0xFF:02X}",
                        ha="center", va="center", fontsize=9, family="monospace", color=SIG)
                s = i

LABEL_X = -int(N * 0.055)
for k, (name, _, _) in enumerate(lanes):
    ax.text(LABEL_X, base_of(k) + lane_h / 2, name, ha="center", va="center",
            fontsize=11, family="monospace")

ax.set_xlim(-int(N * 0.12), N + 40)
ax.set_ylim(-0.3, nlanes * pitch)
ax.set_yticks([])
ax.set_xlabel("clock cycles")
ax.set_title("UART tile: FIFO loopback of 0x5A (50 MHz, 115200 baud)")
for sp in ("top", "right", "left"):
    ax.spines[sp].set_visible(False)
plt.savefig("uart_waveform.svg", bbox_inches="tight", facecolor="white")
print("wrote uart_waveform.svg")
