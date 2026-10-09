"""fig1 -- synthetic annual loss index by region (bar chart, draft).

This figure is a draft with a deliberately planted flaw. Find it by looking
at the figure, not by reading this file.

Run:
    python3 fig1_bar.py
Reads:  ../data/annual_loss_synthetic.csv
Writes: ../figures/fig1_bar_v1.png
"""
import os
import pandas as pd
import matplotlib.pyplot as plt

from common_style import apply_style, left_title

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(HERE, "..", "data"))
FIG_DIR = os.path.normpath(os.path.join(HERE, "..", "figures"))


def draw(df, out_path):
    apply_style()
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(df["region"], df["loss_index"], color="#4c72b0", width=0.6)
    ax.set_ylim(85, 98)
    ax.set_yticks([85, 88, 91, 94, 97])

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
    draw(df, out_path=os.path.join(FIG_DIR, "fig1_bar_v1.png"))
    print(f"check: loss index min/max = {df['loss_index'].min():.1f} / "
          f"{df['loss_index'].max():.1f} ({len(df)} regions)")


if __name__ == "__main__":
    main()
