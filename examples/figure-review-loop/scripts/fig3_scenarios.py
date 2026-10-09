"""fig3 -- synthetic scenario A / B side by side (two heatmaps, draft).

This figure is a draft with a deliberately planted flaw. Find it by looking
at the figure, not by reading this file.

Run:
    python3 fig3_scenarios.py
Reads:  ../data/scenario_ab_synthetic.npz
Writes: ../figures/fig3_scenarios_v1.png
"""
import os
import numpy as np
import matplotlib.pyplot as plt

from common_style import apply_style, left_title

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(HERE, "..", "data"))
FIG_DIR = os.path.normpath(os.path.join(HERE, "..", "figures"))


def draw(a, b, out_path):
    apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    im0 = axes[0].imshow(a, origin="lower", cmap="inferno", extent=[-20, 20, -20, 20])
    fig.colorbar(im0, ax=axes[0], shrink=0.8)
    left_title(axes[0], "Scenario A")

    im1 = axes[1].imshow(b, origin="lower", cmap="inferno", extent=[-20, 20, -20, 20])
    fig.colorbar(im1, ax=axes[1], shrink=0.8)
    left_title(axes[1], "Scenario B")

    for ax in axes:
        ax.set_xlabel("Grid x (km)")
    axes[0].set_ylabel("Grid y (km)")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print("wrote", out_path)


def main():
    npz = np.load(os.path.join(DATA_DIR, "scenario_ab_synthetic.npz"))
    a, b = npz["a"], npz["b"]
    os.makedirs(FIG_DIR, exist_ok=True)
    draw(a, b, os.path.join(FIG_DIR, "fig3_scenarios_v1.png"))
    print(f"check: A max {a.max():.1f}, B max {b.max():.1f} (shape {a.shape})")


if __name__ == "__main__":
    main()
