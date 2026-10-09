"""fig1 -- misleading scale (truncated y-axis on a bar chart).

ANSWER KEY. This file draws only the fixed (v2) figure. The draft (v1)
is drawn by ../../scripts/ with the same file name. Open this only after
you have reviewed the draft yourself.

Draft flaw: the y-axis is truncated to [85, 98] instead of starting at a clean
tick that includes zero. The six regions' loss index actually spans an ~8%
real range (88.5-96.6 on a 0-100 index), but the truncated axis stretches that
into what reads as a 3-4x visual difference between the shortest and tallest
bar. Nothing else about the figure is wrong -- same data, same labels, same
colors in both versions -- so the review loop has exactly one thing to catch.

Fix (v2): y-axis reset to clean ticks starting at 0 (figure-style.md 12-1:
"every axis's start/end must land on a clean tick", generalized here to also
mean "a magnitude-comparison bar chart must not begin above zero" -- otherwise
bar height stops encoding magnitude honestly).

Run:
    python3 fig1_bar.py
Reads:  ../../data/annual_loss_synthetic.csv
Writes: ../figures/fig1_bar_v2.png  (loop-history/figures/)
"""
import os
import pandas as pd
import matplotlib.pyplot as plt

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from common_style import apply_style, clean_bounds, left_title

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLE_DIR = os.path.normpath(os.path.join(HERE, "..", ".."))
DATA_DIR = os.path.join(EXAMPLE_DIR, "data")
FIG_DIR = os.path.normpath(os.path.join(HERE, "..", "figures"))  # loop-history/figures


def draw(df, out_path):
    apply_style()
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(df["region"], df["loss_index"], color="#4c72b0", width=0.6)

    # FIX: the draft set ax.set_ylim(85, 98) -- a floor picked from the data.
    # Bar height only encodes magnitude honestly when the axis starts at zero.
    lo, hi = clean_bounds(0, df["loss_index"].max(), step=20)
    ax.set_ylim(lo, hi)
    ax.set_yticks(range(int(lo), int(hi) + 1, 20))

    left_title(ax, "Synthetic annual loss index by region")
    ax.set_ylabel("Loss index")
    ax.set_xlabel("Region")
    for b, v in zip(bars, df["loss_index"]):
        ax.annotate(f"{v:.1f}", (b.get_x() + b.get_width() / 2, v),
                    textcoords="offset points", xytext=(0, 4),
                    ha="center", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print("wrote", out_path)


def main():
    df = pd.read_csv(os.path.join(DATA_DIR, "annual_loss_synthetic.csv"))
    os.makedirs(FIG_DIR, exist_ok=True)
    draw(df, out_path=os.path.join(FIG_DIR, "fig1_bar_v2.png"))
    spread_pct = (df["loss_index"].max() - df["loss_index"].min()) / df["loss_index"].min() * 100
    print(f"check: real spread across regions = {spread_pct:.1f}% "
          f"(min {df['loss_index'].min():.1f}, max {df['loss_index'].max():.1f})")


if __name__ == "__main__":
    main()
