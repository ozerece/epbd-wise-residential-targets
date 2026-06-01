#!/usr/bin/env python3
"""Generate a map of the 7 selected countries, color-coded by regional group,
with annotation boxes showing sPED, PEF, and dominant heating fuel."""

import warnings
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import geopandas as gpd

warnings.filterwarnings("ignore")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FIGURE_DIR = Path(__file__).resolve().parent.parent / "figures"

# Regional grouping
NORDIC = {"Finland": "FI", "Sweden": "SE"}
WESTERN = {"France": "FR", "Germany": "DE", "Ireland": "IE"}
EASTERN = {"Poland": "PL", "Romania": "RO"}

# Okabe-Ito inspired colors for the three groups
COLOR_NORDIC = "#56B4E9"     # sky blue
COLOR_WESTERN = "#E69F00"    # orange
COLOR_EASTERN = "#009E73"    # bluish green
COLOR_OTHER = "#E8E8E8"      # light gray for non-selected EU countries

# Country annotation data: sPED (kWh/m2, 2020), electricity PEF, dominant fuel
COUNTRY_DATA = {
    "FI": {"sped": 218, "pef": 2.02, "fuel": "District heating"},
    "SE": {"sped": 163, "pef": 1.80, "fuel": "DH, heat pumps"},
    "FR": {"sped": 173, "pef": 2.87, "fuel": "Electric, gas"},
    "DE": {"sped": 167, "pef": 2.27, "fuel": "Gas"},
    "IE": {"sped": 171, "pef": 1.95, "fuel": "Oil, gas"},
    "PL": {"sped": 222, "pef": 2.70, "fuel": "Coal, gas"},
    "RO": {"sped": 211, "pef": 2.52, "fuel": "DH, gas"},
}

LABEL_NAMES = {
    "FI": "Finland", "SE": "Sweden", "FR": "France",
    "DE": "Germany", "IE": "Ireland", "PL": "Poland", "RO": "Romania",
}

# Annotation box positions: (box_x, box_y) in data coords, plus arrow target offset
# These are manually tuned for a clean layout
ANNOTATION_POS = {
    "FI": {"box": (33, 66), "arrow_to": (0, 0)},
    "SE": {"box": (6, 67), "arrow_to": (0, 0)},
    "FR": {"box": (-9, 50), "arrow_to": (2, 2)},
    "DE": {"box": (16, 48), "arrow_to": (0, 2)},
    "IE": {"box": (-11, 56), "arrow_to": (0, 0)},
    "PL": {"box": (27, 55), "arrow_to": (0, 0)},
    "RO": {"box": (31, 44), "arrow_to": (-2, 1)},
}


def main():
    # Match waterfall figure style
    matplotlib.rcParams.update({"font.family": "Lato", "font.weight": 300})

    # Load Natural Earth subunits (10m) for Northern Ireland separation
    su_path = "/tmp/ne_subunits/ne_10m_admin_0_map_subunits.shp"
    world = gpd.read_file(su_path)

    # European subunits for context
    # Filter by bounding box roughly covering Europe
    europe = world.cx[-25:45, 35:75].copy()
    # Remove Russia
    europe = europe[~europe["ADMIN"].str.contains("Russia", case=False, na=False)]

    # Build color mapping by subunit code and name
    su_to_color = {}
    # Map ISO A3 codes for our countries
    iso3_map = {"FI": "FIN", "SE": "SWE", "FR": "FRA", "DE": "DEU",
                "IE": "IRL", "PL": "POL", "RO": "ROU"}
    for name, iso2 in NORDIC.items():
        su_to_color[iso3_map[iso2]] = COLOR_NORDIC
    for name, iso2 in WESTERN.items():
        su_to_color[iso3_map[iso2]] = COLOR_WESTERN
    for name, iso2 in EASTERN.items():
        su_to_color[iso3_map[iso2]] = COLOR_EASTERN
    # Northern Ireland gets Ireland's color (Western Europe)
    su_to_color["NIR"] = COLOR_WESTERN
    # France mainland is FXX, Corsica is FXC in subunits shapefile
    su_to_color["FXX"] = COLOR_WESTERN
    su_to_color["FXC"] = COLOR_WESTERN

    def get_color(row):
        c = su_to_color.get(row["SU_A3"])
        if c:
            return c
        return COLOR_OTHER

    europe["color"] = europe.apply(get_color, axis=1)

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 8))

    # Plot all European countries
    europe.plot(ax=ax, color=europe["color"], edgecolor="white", linewidth=0.6)

    # Build centroid lookup using SU_A3 codes
    # France mainland uses FXX in subunits
    iso2_to_su = {k: iso3_map[k] for k in COUNTRY_DATA}
    iso2_to_su["FR"] = "FXX"
    centroids = {}
    for iso2 in COUNTRY_DATA:
        su3 = iso2_to_su[iso2]
        country = europe[europe["SU_A3"] == su3]
        if not country.empty:
            centroids[iso2] = country.geometry.centroid.iloc[0]

    # Add annotation boxes with leader lines
    bbox_style = dict(boxstyle="round,pad=0.4", facecolor="white",
                      edgecolor="#999999", linewidth=0.8, alpha=0.95)
    _fb = {"family": "Lato", "weight": 600}
    _fn = {"family": "Lato", "weight": 300}

    for iso2, data in COUNTRY_DATA.items():
        cname = LABEL_NAMES[iso2]
        pos = ANNOTATION_POS[iso2]
        box_x, box_y = pos["box"]
        arrow_dx, arrow_dy = pos["arrow_to"]

        # Build annotation text
        text = (f"{cname}\n"
                f"sPED: {data['sped']} kWh/(m\u00b2 yr)\n"
                f"PEF: {data['pef']:.2f}\n"
                f"{data['fuel']}")

        if iso2 in centroids:
            centroid = centroids[iso2]
            target_x = centroid.x + arrow_dx
            target_y = centroid.y + arrow_dy

            ax.annotate(
                text,
                xy=(target_x, target_y),
                xytext=(box_x, box_y),
                fontsize=7, fontfamily="Lato",
                ha="center", va="center",
                bbox=bbox_style,
                arrowprops=dict(arrowstyle="-", color="#999999",
                                linewidth=0.8, connectionstyle="arc3,rad=0.1"),
            )

    # Set map extent to focus on the study area
    ax.set_xlim(-14, 38)
    ax.set_ylim(43, 72)
    ax.set_aspect("equal")
    ax.axis("off")

    # Legend (without "Other EU/EEA" since it clutters)
    legend_patches = [
        mpatches.Patch(facecolor=COLOR_NORDIC, edgecolor="white", label="Nordic"),
        mpatches.Patch(facecolor=COLOR_WESTERN, edgecolor="white", label="Western Europe"),
        mpatches.Patch(facecolor=COLOR_EASTERN, edgecolor="white", label="Eastern Europe"),
    ]
    ax.legend(handles=legend_patches, loc="lower left", frameon=True,
              edgecolor="lightgray", fontsize=8,
              prop={"family": "Lato", "weight": 300})

    fig.tight_layout()

    # Save annotated version
    for ext in ["pdf", "png"]:
        outpath = FIGURE_DIR / f"fig_country_map_annotated.{ext}"
        fig.savefig(outpath, dpi=300, bbox_inches="tight")
        print(f"Saved: {outpath}")

    plt.close(fig)


if __name__ == "__main__":
    main()
