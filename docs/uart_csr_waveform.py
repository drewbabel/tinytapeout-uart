#!/usr/bin/env python3
# Renders uart_csr_waveform.svg from uart_csr_wave.csv. See uart_csr_wave_tb.sv for regen.
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SIG, GREY = "#08306b", "#dfe6ee"
lane_h, gap = 0.72, 0.55
pitch = lane_h + gap

LANES = ["csr_mode", "csr_sclk", "csr_mosi", "psel", "penable", "pwrite", "loopback_en"]
rows = list(csv.DictReader(open("uart_csr_wave.csv")))
N = len(rows)
data = {n: [int(r[n]) for r in rows] for n in LANES}
nlanes = len(LANES)

fig, ax = plt.subplots(figsize=(13, 0.62 * nlanes + 1.4))
base_of = lambda k: (nlanes - 1 - k) * pitch

for k, name in enumerate(LANES):
    base = base_of(k)
    vals = data[name]
    ax.axhline(base, color=GREY, lw=0.8, zorder=0)
    seg = vals + [vals[-1]]
    ax.step(range(N + 1), [base + max(v, 0) * lane_h for v in seg],
            where="post", color=SIG, lw=1.8, zorder=3)

LABEL_X = -int(N * 0.055)
for k, name in enumerate(LANES):
    ax.text(LABEL_X, base_of(k) + lane_h / 2, name, ha="center", va="center",
            fontsize=11, family="monospace")

ax.set_xlim(-int(N * 0.12), N)
ax.set_ylim(-0.3, nlanes * pitch)
ax.set_yticks([])
ax.set_xlabel("clock cycles")
ax.set_title("CSR write: serial frame into apb_csr (CTRL bit0)")
for sp in ("top", "right", "left"):
    ax.spines[sp].set_visible(False)
plt.savefig("uart_csr_waveform.svg", bbox_inches="tight", facecolor="white")
print("wrote uart_csr_waveform.svg")
