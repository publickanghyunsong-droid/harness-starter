"""Shared plotting style for the figure-review-loop example set.

Why this file exists
---------------------
figure-style.md 12-0 (the style guide this example set follows) requires that any
element shared across multiple figures — colormap, scale, tick convention — be
implemented once and reused, not re-derived per script. This module is that single
reusable helper for the three example figures in this folder. If you change a shared
convention (e.g. the "blog" font scale), change it here once; all three fig*.py
scripts import from here and will pick it up on next run.

Labels are English by default (figure-style.md 12-4: new figures default to English),
which also sidesteps a real portability problem: Korean rendering depends on a CJK
font (AppleGothic / NanumGothic / Malgun Gothic) being installed on the machine that
runs the script. A public example repo cannot assume that. Keeping chart text in
English means the figures render identically on any reader's machine with only
matplotlib's default fonts.
"""
import numpy as np
import matplotlib.pyplot as plt

# Matplotlib rcParams style bucket for a screen/report context ("blog" scale in the
# parent house-style vocabulary: larger fonts than a print-journal figure). Kept as a
# module constant, not re-typed per script.
STYLE = {
    "font.size": 13,
    "axes.titlesize": 15,
    "axes.titleweight": "normal",
    "axes.labelsize": 13,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "legend.fontsize": 11,
    "figure.titlesize": 17,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.dpi": 150,
    "savefig.facecolor": "white",
    "axes.linewidth": 0.8,
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
}


def apply_style():
    plt.rcParams.update(STYLE)


def clean_bounds(data_min, data_max, step):
    """Round (data_min, data_max) outward to the nearest multiple of `step`.

    This is the figure-style 12-1 rule ("every axis/colorbar start and end must
    land on a clean tick, not on the raw data min/max") implemented once so all
    three figures apply it identically.
    """
    lo = np.floor(data_min / step) * step
    hi = np.ceil(data_max / step) * step
    if hi == lo:
        hi = lo + step
    return lo, hi


def left_title(ax, text):
    """subplot titles are left-aligned, symbolic (variable + minimal metadata),
    never a narrative sentence with an arrow/implication (figure-style 12-2/12-3)."""
    ax.set_title(text, loc="left")
