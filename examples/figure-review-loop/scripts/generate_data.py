"""Generate the small synthetic datasets used by fig1/fig2/fig3.

All three datasets in this example are SYNTHETIC — invented with a fixed random
seed, not sampled from any real hazard model or loss database. That is a
deliberate choice, not a shortcut: this example set exists specifically because
the original (real) case this workthrough was drafted from could not clear
publication review, and the project decision was to rebuild the case on data
that is safe to publish from the start (see ../README.md).

Run:
    python3 generate_data.py

Output (written to ../data/, relative to this script):
    annual_loss_synthetic.csv   -- fig1
    hazard_grid_synthetic.npy   -- fig2
    scenario_ab_synthetic.npz   -- fig3

Reproducibility: single RNG seed (42) drives all three datasets in this one
script, in this order, so re-running produces byte-identical output every
time. See run_manifest.md for the sha256 checksums to check against.
"""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(HERE, "..", "data"))
SEED = 42


def make_annual_loss(rng):
    """fig1 input: a synthetic annual loss index for 6 example regions."""
    regions = ["Region A", "Region B", "Region C", "Region D", "Region E", "Region F"]
    base = np.array([88.5, 90.1, 91.8, 93.4, 95.0, 96.6])
    noise = rng.normal(0, 0.4, size=len(regions))
    loss_index = np.round(base + noise, 1)
    df = pd.DataFrame({"region": regions, "loss_index": loss_index})
    return df


def make_hazard_grid(rng):
    """fig2 input: a synthetic 40x40 hazard-intensity field (one Gaussian bump
    + background noise), loosely styled after a gridded model hazard field
    but with invented numbers -- not a real hazard run.
    """
    n = 40
    x = np.linspace(-20, 20, n)
    y = np.linspace(-20, 20, n)
    xx, yy = np.meshgrid(x, y)
    bump = 42 * np.exp(-((xx - 5) ** 2 + (yy + 3) ** 2) / (2 * 8.0 ** 2))
    field = 12 + bump + rng.normal(0, 1.5, size=(n, n))
    field = np.clip(field, 0, None)
    return field


def make_scenario_ab(rng):
    """fig3 input: two synthetic scenario grids (A, B) of the same shape."""
    n = 40
    x = np.linspace(-20, 20, n)
    y = np.linspace(-20, 20, n)
    xx, yy = np.meshgrid(x, y)

    bump_a = 34 * np.exp(-((xx + 4) ** 2 + (yy - 2) ** 2) / (2 * 7.0 ** 2))
    field_a = 8 + bump_a + rng.normal(0, 1.2, size=(n, n))

    bump_b = 37 * np.exp(-((xx - 6) ** 2 + (yy + 4) ** 2) / (2 * 7.5 ** 2))
    field_b = 8 + bump_b + rng.normal(0, 1.2, size=(n, n))

    field_a = np.clip(field_a, 0, None)
    field_b = np.clip(field_b, 0, None)
    return field_a, field_b


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    rng = np.random.default_rng(SEED)

    df = make_annual_loss(rng)
    df.to_csv(os.path.join(DATA_DIR, "annual_loss_synthetic.csv"), index=False)

    grid = make_hazard_grid(rng)
    np.save(os.path.join(DATA_DIR, "hazard_grid_synthetic.npy"), grid)

    field_a, field_b = make_scenario_ab(rng)
    np.savez(os.path.join(DATA_DIR, "scenario_ab_synthetic.npz"), a=field_a, b=field_b)

    print("wrote:")
    print(" ", os.path.join(DATA_DIR, "annual_loss_synthetic.csv"))
    print("   ", df.to_string(index=False))
    print(" ", os.path.join(DATA_DIR, "hazard_grid_synthetic.npy"),
          "shape", grid.shape, "min/max", round(grid.min(), 1), round(grid.max(), 1))
    print(" ", os.path.join(DATA_DIR, "scenario_ab_synthetic.npz"),
          "A max", round(field_a.max(), 1), "B max", round(field_b.max(), 1))


if __name__ == "__main__":
    main()
