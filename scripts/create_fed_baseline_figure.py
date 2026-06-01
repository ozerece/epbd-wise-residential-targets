#!/usr/bin/env python3
"""Generate a consolidated 2020 FED carrier mix figure for all 7 countries."""

import warnings
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FIGURE_DIR = Path(__file__).resolve().parent.parent / "figures"
OUTPUT1_FILE = DATA_DIR / "output_1_all.xlsx"

COUNTRIES = ["Finland", "France", "Germany", "Ireland", "Poland", "Romania", "Sweden"]

# Simplified carrier grouping for a clean overview figure
CARRIER_GROUPS = {
    "Coal": ["coal"],
    "Oil": ["oil", "oil from RES"],
    "Gas": ["gas", "gas from RES"],
    "Electricity": ["electricity", "electricity from RES"],
    "District heating": ["district heating", "district heating from RES"],
    "Biomass": ["biomass"],
    "Ambient & solar": ["ambient heat", "solar thermal", "pv space heating & dhw"],
}

# Fossil fuels in grey/black shadings; other carriers in distinct colours
CARRIER_COLORS = {
    "Coal": "#2d2d2d",           # near black
    "Oil": "#6b6b6b",            # medium grey
    "Gas": "#a8a8a8",            # light grey
    "Electricity": "#d64550",    # muted red
    "District heating": "#4a90c4",  # steel blue
    "Biomass": "#5ba05b",        # forest green
    "Ambient & solar": "#e8a838",   # amber
}

CARRIER_ORDER = ["Coal", "Oil", "Gas", "Electricity", "District heating", "Biomass", "Ambient & solar"]


def main():
    # Match waterfall figure style (Lato, weight 300)
    _fp = {"family": "Lato", "weight": 300}
    _fb = {"family": "Lato", "weight": 600}
    matplotlib.rcParams.update({"font.family": "Lato", "font.weight": 300})

    plt.rcParams.update({
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 8,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.spines.top": False,
        "axes.spines.right": False,
    })

    print("Loading data...")
    df = pd.read_excel(OUTPUT1_FILE)

    # Filter: FED, Residential, 2020, one scenario (all same at baseline)
    fed = df[
        (df["data_type_id"] == "FED") &
        (df["sector_id"] == "Residential") &
        (df["year"] == 2020)
    ].copy()

    # Take first available scenario per country (all identical at 2020)
    fed = fed.groupby(["nuts0_id", "energy_carrier_id"])["value"].first().reset_index()

    # Build grouped data
    data = {}
    for group, carriers in CARRIER_GROUPS.items():
        vals = []
        for country in COUNTRIES:
            v = fed[(fed["nuts0_id"] == country) &
                    (fed["energy_carrier_id"].isin(carriers))]["value"].sum()
            vals.append(v)
        data[group] = np.array(vals)

    # Compute totals and percentages
    totals = np.zeros(len(COUNTRIES))
    for group in CARRIER_ORDER:
        totals += data[group]

    data_pct = {}
    for group in CARRIER_ORDER:
        data_pct[group] = (data[group] / totals) * 100

    # Create figure
    fig, ax = plt.subplots(figsize=(8, 4.5))

    x = np.arange(len(COUNTRIES))
    width = 0.58
    bottom = np.zeros(len(COUNTRIES))

    for group in CARRIER_ORDER:
        vals = data_pct[group]
        ax.bar(x, vals, width, bottom=bottom,
               color=CARRIER_COLORS[group],
               edgecolor="white", linewidth=0.5,
               label=group)
        # Add percentage labels for segments > 4%
        for i, (v, b) in enumerate(zip(vals, bottom)):
            if v > 4:
                ax.text(x[i], b + v / 2, f"{v:.0f}%",
                        ha="center", va="center", fontsize=7,
                        fontproperties=_fb, color="white")
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(COUNTRIES, fontsize=9, fontproperties=_fp)
    ax.set_ylabel("Share of energy carriers in the final energy demand [%]", fontsize=9, fontproperties=_fp)
    ax.set_ylim(0, 105)
    ax.tick_params(axis="y", labelsize=8)

    # Legend below figure
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08),
              ncol=4, frameon=True, edgecolor="lightgray", fontsize=8,
              prop={"family": "Lato", "weight": 300})

    # Save
    for ext in ["pdf", "png"]:
        outpath = FIGURE_DIR / f"fig_fed_baseline_2020.{ext}"
        fig.savefig(outpath, dpi=300, bbox_inches="tight")
        print(f"Saved: {outpath}")

    plt.close(fig)

    # Print data for verification
    print("\n2020 Residential FED mix (%):")
    print(f"{'Country':<12}", end="")
    for g in CARRIER_ORDER:
        print(f"{g:<18}", end="")
    print()
    for i, country in enumerate(COUNTRIES):
        print(f"{country:<12}", end="")
        for g in CARRIER_ORDER:
            print(f"{data_pct[g][i]:>6.1f}%{'':>10}", end="")
        print()


if __name__ == "__main__":
    main()
