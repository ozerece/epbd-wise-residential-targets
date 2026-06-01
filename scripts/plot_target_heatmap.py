#!/usr/bin/env python3
"""Generate separate heatmaps for 2030 and 2035 target achievement."""

import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from pathlib import Path

matplotlib.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Lato", "DejaVu Sans"],
    "font.weight": "light",
    "font.size": 10,
    "figure.dpi": 300,
})

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FIGURE_DIR = Path(__file__).resolve().parent.parent / "figures"

# Use the unified loader so country/scenario/PEF naming is consistent
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from create_figures import load_target2

df = load_target2()
sped = df[(df["data_type_id"] == "area-specific PED_incl_sf") & (df["sector_id"] == "Residential")]
grouped = sped.groupby(["nuts0_id", "scenario_id", "PEF", "year"])["value"].mean().reset_index()

countries = ["Finland", "France", "Germany", "Ireland", "Poland", "Romania", "Sweden"]
scenarios = ["Regulatory+", "Regulatory", "Moderate", "Economics+"]
scenario_labels = ["Regulatory+", "Regulatory", "Moderate", "Economics"]
pef_types = ["constant", "decreasing"]
pef_labels = ["Constant PEF", "Decreasing PEF"]
targets = {2030: 16, 2035: 20}

results = {}
all_vals = {2030: [], 2035: []}
for country in countries:
    for scenario in scenarios:
        for pef in pef_types:
            for year in [2030, 2035]:
                base = grouped[(grouped["nuts0_id"] == country) &
                              (grouped["scenario_id"] == scenario) &
                              (grouped["PEF"] == pef) &
                              (grouped["year"] == 2020)]["value"].values
                val = grouped[(grouped["nuts0_id"] == country) &
                             (grouped["scenario_id"] == scenario) &
                             (grouped["PEF"] == pef) &
                             (grouped["year"] == year)]["value"].values
                if len(base) > 0 and len(val) > 0:
                    pct = (base[0] - val[0]) / base[0] * 100
                    results[(country, scenario, pef, year)] = pct
                    all_vals[year].append(pct)


def get_color(pct, year):
    target = targets[year]
    vmin_y = min(all_vals[year])
    vmax_y = max(all_vals[year])
    if pct >= target:
        # Green shades: light green at target, dark green further above
        ratio = min((pct - target) / (vmax_y - target), 1.0) if vmax_y > target else 0
        r = int(180 - ratio * 154)
        g = int(220 - ratio * 90)
        b = int(180 - ratio * 154)
        return f"#{r:02x}{g:02x}{b:02x}"
    else:
        # Red shades: light red at target, dark red further below
        ratio = min((target - pct) / (target - vmin_y), 1.0) if target > vmin_y else 0
        r = int(240 - ratio * 57)
        g = int(170 - ratio * 142)
        b = int(170 - ratio * 142)
        return f"#{r:02x}{g:02x}{b:02x}"


def text_color(pct, year):
    target = targets[year]
    vmin_y = min(all_vals[year])
    vmax_y = max(all_vals[year])
    if pct >= target:
        ratio = min((pct - target) / (vmax_y - target), 1.0) if vmax_y > target else 0
        return "white" if ratio > 0.5 else "black"
    else:
        ratio = min((target - pct) / (target - vmin_y), 1.0) if target > vmin_y else 0
        return "white" if ratio > 0.5 else "black"


# Two-tone colormap: dark red → light red | light green → dark green
colors_list = ["#b71c1c", "#e57373", "#f0aaaa", "#b4dcb4", "#5aae61", "#1a7837"]
nodes = [0.0, 0.25, 0.49, 0.51, 0.75, 1.0]
cmap = mcolors.LinearSegmentedColormap.from_list("target", list(zip(nodes, colors_list)))


def make_heatmap(year, filename):
    target = targets[year]
    target_label = "16%" if year == 2030 else "20\u201322%"
    vmin_y = int(np.floor(min(all_vals[year])))
    vmax_y = int(np.ceil(max(all_vals[year])))

    n_rows = len(countries)
    n_cols = 8

    fig, ax = plt.subplots(figsize=(8, 4.5))

    # Build color matrix
    data = np.zeros((n_rows, n_cols))
    color_matrix = np.zeros((n_rows, n_cols, 3))

    for ci, country in enumerate(countries):
        for pi, pef in enumerate(pef_types):
            for si, scenario in enumerate(scenarios):
                col = pi * 4 + si
                pct = results.get((country, scenario, pef, year), 0)
                data[ci, col] = pct
                color_matrix[ci, col] = matplotlib.colors.to_rgb(get_color(pct, year))

    ax.imshow(color_matrix, aspect="auto", interpolation="nearest")

    # Cell text
    for ci in range(n_rows):
        for col in range(n_cols):
            pct = data[ci, col]
            tc = text_color(pct, year)
            ax.text(col, ci, f"{pct:.0f}%", ha="center", va="center",
                   fontsize=9, fontweight="bold", color=tc)

    # White grid lines
    for ci in range(n_rows + 1):
        ax.axhline(y=ci - 0.5, color="white", linewidth=1.5)
    for col in range(n_cols + 1):
        ax.axvline(x=col - 0.5, color="white", linewidth=1.5)

    # Separator between constant and decreasing
    ax.axvline(x=3.5, color="gray", linewidth=2, alpha=0.4, linestyle="--")

    # Country labels
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(countries, fontsize=10)
    ax.tick_params(left=False, bottom=False)

    # Scenario labels
    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(scenario_labels * 2, fontsize=7, fontweight="bold",
                       color="gray", rotation=35, ha="right")

    # PEF labels — tighter to the heatmap
    ax.text(1.5, -1.2, pef_labels[0], ha="center", va="bottom", fontsize=9.5, fontweight="bold")
    ax.text(5.5, -1.2, pef_labels[1], ha="center", va="bottom", fontsize=9.5, fontweight="bold")

    ax.spines[:].set_visible(False)

    # Colorbar
    pos = ax.get_position()
    cbar_ax = fig.add_axes([pos.x1 + 0.02, pos.y0 + pos.height * 0.15,
                             0.015, pos.height * 0.7])

    norm = mcolors.TwoSlopeNorm(vcenter=target, vmin=vmin_y, vmax=vmax_y)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, cax=cbar_ax, orientation="vertical")

    cbar.set_ticks([vmin_y, vmax_y])
    cbar.set_ticklabels([f"{vmin_y}%", f"{vmax_y}%"])
    cbar.ax.tick_params(labelsize=7, length=2, pad=2)
    for label in cbar.ax.get_yticklabels():
        label.set_fontweight("bold")

    cbar_ax.axhline(y=target, color="black", linewidth=1.5, linestyle="-")
    cbar_ax.annotate(f" {target_label}\n (target)", xy=(1, target),
                    xycoords=("axes fraction", "data"),
                    fontsize=5.5, fontweight="bold", va="center", ha="left",
                    annotation_clip=False)

    for ext in ["pdf", "png"]:
        outpath = FIGURE_DIR / f"{filename}.{ext}"
        fig.savefig(outpath, dpi=300, bbox_inches="tight")
        print(f"Saved: {outpath}")

    plt.close(fig)


make_heatmap(2030, "fig_target_heatmap_2030")
make_heatmap(2035, "fig_target_heatmap_2035")
