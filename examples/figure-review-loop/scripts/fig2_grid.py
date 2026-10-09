"""fig2 -- synthetic gridded field (heatmap + colorbar, draft).

This figure is a draft with a deliberately planted flaw. Find it by looking
at the figure, not by reading this file.

Run:
    python3 fig2_grid.py
Reads:  ../data/hazard_grid_synthetic.npy
Writes: ../figures/fig2_grid_v1.png
"""
import os
import numpy as np
import matplotlib.pyplot as plt

from common_style import apply_style, clean_bounds, left_title

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(HERE, "..", "data"))
FIG_DIR = os.path.normpath(os.path.join(HERE, "..", "figures"))


def draw(grid, out_path):
    apply_style()
    fig, ax = plt.subplots(figsize=(6, 5.5))
    lo, hi = clean_bounds(0, grid.max(), step=10)
    im = ax.imshow(grid, origin="lower", cmap="viridis", vmin=lo, vmax=hi)
    fig.colorbar(im, ax=ax, shrink=0.85, ticks=range(int(lo), int(hi) + 1, 10))
    left_title(ax, "Hazard map")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print("wrote", out_path)


def main():
    grid = np.load(os.path.join(DATA_DIR, "hazard_grid_synthetic.npy"))
    os.makedirs(FIG_DIR, exist_ok=True)
    draw(grid, os.path.join(FIG_DIR, "fig2_grid_v1.png"))
    print(f"check: grid min/max = {grid.min():.1f} / {grid.max():.1f} "
          f"(shape {grid.shape})")


if __name__ == "__main__":
    main()
