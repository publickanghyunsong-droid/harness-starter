"""fig2 -- missing colorbar units/label on a gridded field.

ANSWER KEY. This file draws only the fixed (v2) figure. The draft (v1)
is drawn by ../../scripts/ with the same file name. Open this only after
you have reviewed the draft yourself.

Draft flaw: the colorbar shows numbers (0-60) but no label telling the
reader what those numbers are or what unit they're in -- could be wind speed,
a normalized index, a percentage, anything. The axes are similarly unlabeled
(just "x" and "y"). Same underlying field, same colormap, same colorbar
position in both versions -- the only difference is whether the reader can
tell what they're looking at.

Fix (v2): colorbar gets a label with explicit unit ("Wind speed (m/s)"),
axis labels get units, and the colorbar bounds are reset to clean ticks per
figure-style.md 12-1 (0, 60 -> ticks at 0/10/20/30/40/50/60 rather than the raw
data min/max).

Run:
    python3 fig2_grid.py
Reads:  ../../data/hazard_grid_synthetic.npy
Writes: ../figures/fig2_grid_v2.png  (loop-history/figures/)
"""
import os
import numpy as np
import matplotlib.pyplot as plt

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from common_style import apply_style, clean_bounds, left_title

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLE_DIR = os.path.normpath(os.path.join(HERE, "..", ".."))
DATA_DIR = os.path.join(EXAMPLE_DIR, "data")
FIG_DIR = os.path.normpath(os.path.join(HERE, "..", "figures"))  # loop-history/figures


def draw_fixed(grid, out_path):
    apply_style()
    fig, ax = plt.subplots(figsize=(6, 5.5))
    lo, hi = clean_bounds(0, grid.max(), step=10)
    im = ax.imshow(grid, origin="lower", cmap="viridis", vmin=lo, vmax=hi,
                    extent=[-20, 20, -20, 20])
    cbar = fig.colorbar(im, ax=ax, shrink=0.85, ticks=range(int(lo), int(hi) + 1, 10))
    cbar.set_label("Wind speed (m/s)")
    left_title(ax, "Synthetic hazard field (example grid)")
    ax.set_xlabel("Grid x (km)")
    ax.set_ylabel("Grid y (km)")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print("wrote", out_path)


def main():
    grid = np.load(os.path.join(DATA_DIR, "hazard_grid_synthetic.npy"))
    os.makedirs(FIG_DIR, exist_ok=True)
    draw_fixed(grid, os.path.join(FIG_DIR, "fig2_grid_v2.png"))
    print(f"check: grid min/max = {grid.min():.1f} / {grid.max():.1f} "
          f"(shape {grid.shape})")


if __name__ == "__main__":
    main()
