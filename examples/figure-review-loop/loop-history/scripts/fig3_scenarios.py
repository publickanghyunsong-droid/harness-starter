"""fig3 -- incomparable A/B panels (independently autoscaled color limits).

ANSWER KEY. This file draws only the fixed (v2) figure. The draft (v1)
is drawn by ../../scripts/ with the same file name. Open this only after
you have reviewed the draft yourself.

Draft flaw: scenario A and scenario B are plotted side by side, each with its
own colormap autoscaled to its own min/max. In truth, B's peak intensity is
only about 8% higher than A's (34 vs 37 synthetic units) -- but because each
panel stretches its own color range to fill the same visual palette, both
hotspots look equally "deep red" and equally sized. A reader cannot tell from
the picture whether A and B differ by 8% or by 800%; the two panels are not
actually comparable even though they are drawn next to each other.

Fix (v2): both panels share one color scale (same vmin/vmax, figure-style.md
12-5: "A/B comparison must be a real comparison -- shared color scale"), and a
third panel adds the actual difference field (B - A) on a diverging colormap
centered at zero, per the same rule. That third panel is where the true 8%
difference and its spatial pattern become visible.

Run:
    python3 fig3_scenarios.py
Reads:  ../../data/scenario_ab_synthetic.npz
Writes: ../figures/fig3_scenarios_v2.png  (loop-history/figures/)
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


def draw_fixed(a, b, out_path):
    apply_style()
    # (a)(b)(c) are built as three axes in ONE gridspec row, so their
    # height is fixed by the gridspec row height, not by whatever colorbar
    # happens to be attached to each one. Each colorbar gets its OWN axes
    # (cax=...) in a separate gridspec cell instead of being carved out of
    # ax_a/ax_b/ax_c via fig.colorbar(ax=...) -- that carving is what caused
    # the (a)(b) vs (c) height/title misalignment in the first render
    # (shared bottom colorbar shrinks a,b one way; a lone right colorbar
    # shrinks c a different way). Fixed here per figure-style.md 12-2 frame
    # align: put shared elements in dedicated axes so panel geometry is
    # identical regardless of which colorbar layout each panel uses.
    fig = plt.figure(figsize=(15, 5.8))
    gs = fig.add_gridspec(nrows=2, ncols=5,
                           width_ratios=[1, 1, 0.15, 1, 0.045],
                           height_ratios=[1, 0.055],
                           wspace=0.3, hspace=0.4)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[0, 3])
    cax_c = fig.add_subplot(gs[0, 4])
    cax_ab = fig.add_subplot(gs[1, 0:2])

    lo, hi = clean_bounds(0, max(a.max(), b.max()), step=10)
    im0 = ax_a.imshow(a, origin="lower", cmap="inferno", vmin=lo, vmax=hi,
                       extent=[-20, 20, -20, 20])
    left_title(ax_a, "(a) Scenario A")

    im1 = ax_b.imshow(b, origin="lower", cmap="inferno", vmin=lo, vmax=hi,
                       extent=[-20, 20, -20, 20])
    left_title(ax_b, "(b) Scenario B")
    fig.colorbar(im1, cax=cax_ab, orientation="horizontal",
                 ticks=range(int(lo), int(hi) + 1, 10),
                 label="Wind speed (m/s)")

    diff = b - a
    dmax = clean_bounds(0, np.abs(diff).max(), step=5)[1]
    im2 = ax_c.imshow(diff, origin="lower", cmap="RdBu_r", vmin=-dmax, vmax=dmax,
                       extent=[-20, 20, -20, 20])
    left_title(ax_c, "(c) Difference : B - A")
    fig.colorbar(im2, cax=cax_c, label="Wind speed difference (m/s)")

    for ax in (ax_a, ax_b, ax_c):
        ax.set_xlabel("Grid x (km)")
    ax_a.set_ylabel("Grid y (km)")

    fig.savefig(out_path)
    plt.close(fig)
    print("wrote", out_path)


def main():
    npz = np.load(os.path.join(DATA_DIR, "scenario_ab_synthetic.npz"))
    a, b = npz["a"], npz["b"]
    os.makedirs(FIG_DIR, exist_ok=True)
    draw_fixed(a, b, os.path.join(FIG_DIR, "fig3_scenarios_v2.png"))
    pct = (b.max() - a.max()) / a.max() * 100
    print(f"check: true peak difference = {pct:.1f}% (A max {a.max():.1f}, B max {b.max():.1f})")


if __name__ == "__main__":
    main()
