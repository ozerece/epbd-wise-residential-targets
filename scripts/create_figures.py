#!/usr/bin/env python3
"""Generate publication-quality figures for the EPBD WISE paper."""

import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

# =============================================================================
# Configuration
# =============================================================================

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FIGURE_DIR = Path(__file__).resolve().parent.parent / "figures"
FIGURE_DIR.mkdir(exist_ok=True)
WATERFALL_DIR = FIGURE_DIR / "waterfall_updated"
WATERFALL_DIR.mkdir(exist_ok=True)

OUTPUT1_FILE = DATA_DIR / "output_1_all.xlsx"
TARGET2_FILE = DATA_DIR / "output_1_all.xlsx"
COSTS3_FILE = DATA_DIR / "costs_3_all.xlsx"

OUTPUT1_EXISTING_FILE = DATA_DIR / "output_1_existing.xlsx"
TARGET2_EXISTING_FILE = DATA_DIR / "output_1_existing.xlsx"
COSTS3_EXISTING_FILE = DATA_DIR / "costs_3_existing.xlsx"

# Mapping from original_scenario_name in existing files to (scenario_id, PEF)
_EXISTING_SCENARIO_MAP = {
    # Regulatory+: 75 EUR/t, MEPS, no new fossil
    "8_nofoss_co2_75_install_iopt_MEPS_sub": ("Regulatory+", "constant"),
    "8_nofoss_co2_75_install_iopt_MEPS": ("Regulatory+", "constant"),
    "9_nofoss_co2_75_low_pef_install_iopt_MEPS_sub": ("Regulatory+", "decreasing"),
    "9_nofoss_co2_75_low_pef_install_iopt_MEPS": ("Regulatory+", "decreasing"),
    # Regulatory: 75 EUR/t, MEPS
    "4_low_pol_co2_75_install_iopt_MEPS_sub": ("Regulatory", "constant"),
    "4_low_pol_co2_75_install_iopt_MEPS": ("Regulatory", "constant"),
    "5_low_pol_co2_75_low_pef_install_iopt_MEPS_sub": ("Regulatory", "decreasing"),
    "5_low_pol_co2_75_low_pef_install_iopt_MEPS": ("Regulatory", "decreasing"),
    # Moderate: 75 EUR/t, no residential MEPS (preferred)
    "4_low_pol_co2_75_install_iopt_noMEPS": ("Moderate", "constant"),
    "5_low_pol_co2_75_low_pef_install_iopt_noMEPS": ("Moderate", "decreasing"),
    # Economics+: 300 EUR/t, no MEPS
    "6_co2_300_install_iopt_noMEPS": ("Economics+", "constant"),
    "7_co2_300_low_pef_install_iopt_noMEPS": ("Economics+", "decreasing"),
    "6_co2_300_install_iopt_MEPS_sub": ("Economics+", "constant"),
    "7_co2_300_low_pef_install_iopt_MEPS_sub": ("Economics+", "decreasing"),
    "6_co2_300_install_iopt_MEPS": ("Economics+", "constant"),
    "7_co2_300_low_pef_install_iopt_MEPS": ("Economics+", "decreasing"),
    # Poland-specific Economics+ uses the _ab variant
    "6_co2_300_ab": ("Economics+", "constant"),
    "7_co2_300_low_pef_ab": ("Economics+", "decreasing"),
    # No policy scenarios (2_/3_) are intentionally NOT mapped here, so
    # they are dropped during loading and never enter the analysis.
}

COUNTRIES = ["Finland", "France", "Germany", "Ireland", "Poland", "Romania", "Sweden"]

SCENARIOS = ["No policy", "Regulatory+", "Regulatory", "Moderate", "Economics+"]
POLICY_SCENARIOS = ["Regulatory+", "Regulatory", "Moderate", "Economics+"]

PEF_TYPES = ["constant", "decreasing"]
DISPLAY_YEARS = [2020, 2025, 2030, 2035, 2040, 2045, 2050]

# Energy carrier colors — intuitive scheme:
#   Fossil conventional: dark warm tones
#   Fossil from RES: lighter versions of same hue
#   Electricity: red family
#   District heating: blue family
#   Renewables: greens/yellows
CARRIER_COLORS = {
    # Fossil conventional (dark)
    "coal": "#2d2d2d",
    "oil": "#8c510a",
    "gas": "#bf812d",
    # Fossil from RES (lighter counterparts)
    "oil from RES": "#dfc27d",
    "gas from RES": "#f6e8c3",
    # Electricity (red family)
    "electricity": "#c0392b",
    "electricity from RES": "#e74c3c",
    # District heating (blue family)
    "district heating": "#1a5276",
    "district heating from RES": "#5dade2",
    # Renewables (greens/yellows)
    "biomass": "#27ae60",
    "ambient heat": "#76d7c4",
    "solar thermal": "#f4d03f",
    "pv space heating & dhw": "#a3e048",
}

CARRIER_ORDER = [
    "coal", "oil", "oil from RES", "gas", "gas from RES",
    "electricity", "electricity from RES",
    "district heating", "district heating from RES",
    "biomass", "ambient heat", "solar thermal", "pv space heating & dhw",
]

SCENARIO_COLORS = {
    "Regulatory+": "#e6550d",
    "Regulatory": "#3182bd",
    "Moderate": "#969696",
    "Mix": "#31a354",
    "Economics+": "#1f3d73",
    "No policy": "#bdbdbd",
}

PEF_BAR_COLORS = {
    "constant": "#3182bd",
    "decreasing": "#e6550d",
}


# =============================================================================
# Matplotlib style
# =============================================================================

def setup_style():
    plt.rcParams.update({
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "font.family": "sans-serif",
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 8,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.grid": True,
        "grid.alpha": 0.3,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


# =============================================================================
# Data loading with deduplication
# =============================================================================

def load_output1():
    """Load all-buildings data with scenario mapping and PEF column added.

    output_1_all.xlsx now uses the same schema as target_indicators_2_*,
    so we apply the same processing here: country normalisation, residential
    filter, scenario mapping to paper labels with PEF column, dedup, and
    Moderate fallback for countries without separate Moderate runs.
    """
    df = pd.read_excel(OUTPUT1_FILE)
    df = _normalise_country_names(df)
    df = df[df["nuts0_id"].isin(COUNTRIES)].copy()
    df = df[df["sector_id"] == "Residential"].copy()
    df["_mapped"] = df["original_scenario_name"].map(_EXISTING_SCENARIO_MAP)
    df = df.dropna(subset=["_mapped"]).copy()
    df["scenario_id"] = df["_mapped"].apply(lambda x: x[0])
    df["PEF"] = df["_mapped"].apply(lambda x: x[1])
    df.drop(columns=["_mapped", "original_scenario_name"],
            errors="ignore", inplace=True)
    key_cols = [c for c in df.columns if c != "value"]
    df = df.drop_duplicates(subset=key_cols, keep="first").reset_index(drop=True)
    df = _ensure_moderate_fallback(df)
    return df


def _normalise_country_names(df):
    """Normalise country labels and exclude Ukraine."""
    rename_map = {
        "Poland (updated building stock)": "Poland",
        "Romania (updated building stock)": "Romania",
    }
    df["nuts0_id"] = df["nuts0_id"].replace(rename_map)
    df = df[df["nuts0_id"] != "Ukraine"].copy()
    return df


def _ensure_moderate_fallback(df):
    """Ensure every country/PEF has a Moderate scenario.

    The Moderate scenario should ideally come from the noMEPS run
    (4_low_pol_co2_75_install_iopt_noMEPS). If it does not exist for
    a particular country/PEF, fall back to the Regulatory data
    (4_low_pol_co2_75_install_iopt_MEPS_sub) — i.e. treat Moderate as
    equivalent to Regulatory for that country/PEF.
    """
    if "scenario_id" not in df.columns or "PEF" not in df.columns:
        return df
    have_pairs = set(
        df[df["scenario_id"] == "Moderate"]
        .groupby(["nuts0_id", "PEF"]).size().index
    )
    reg_pairs = set(
        df[df["scenario_id"] == "Regulatory"]
        .groupby(["nuts0_id", "PEF"]).size().index
    )
    missing = reg_pairs - have_pairs
    if not missing:
        return df
    fallback_rows = []
    for ctry, pef in missing:
        sub = df[
            (df["nuts0_id"] == ctry)
            & (df["PEF"] == pef)
            & (df["scenario_id"] == "Regulatory")
        ].copy()
        sub["scenario_id"] = "Moderate"
        fallback_rows.append(sub)
    if fallback_rows:
        df = pd.concat([df] + fallback_rows, ignore_index=True)
    return df


def load_target2():
    """Hybrid loader for the all-buildings file.

    Reads the new output_1_all.xlsx (full data for 6 countries, missing
    Sweden) plus the older target_indicators_2_all.xlsx (which still has
    Sweden). For any country present in the new file, the new data wins;
    for countries missing from the new file (today, Sweden) the old file
    fills in. Once Sweden is added to output_1_all.xlsx, the fallback can
    be retired.
    """
    df_new = pd.read_excel(TARGET2_FILE)
    df_new = _normalise_country_names(df_new)
    new_countries = set(df_new["nuts0_id"].unique())

    fallback_path = DATA_DIR / "target_indicators_2_all.xlsx"
    if fallback_path.exists() and fallback_path != TARGET2_FILE:
        df_old = pd.read_excel(fallback_path)
        df_old = _normalise_country_names(df_old)
        df_old = df_old[~df_old["nuts0_id"].isin(new_countries)].copy()
        df = pd.concat([df_new, df_old], ignore_index=True)
    else:
        df = df_new

    # Filter to our countries and residential sector only
    df = df[df["nuts0_id"].isin(COUNTRIES)].copy()
    df = df[df["sector_id"] == "Residential"].copy()
    # Map original_scenario_name to (paper label, PEF type)
    df["_mapped"] = df["original_scenario_name"].map(_EXISTING_SCENARIO_MAP)
    df = df.dropna(subset=["_mapped"]).copy()
    df["scenario_id"] = df["_mapped"].apply(lambda x: x[0])
    df["PEF"] = df["_mapped"].apply(lambda x: x[1])
    df.drop(columns=["_mapped", "original_scenario_name"],
            errors="ignore", inplace=True)
    # Drop duplicates that arise when the same original scenario appears
    # multiple times mapped to the same paper label
    key_cols = [c for c in df.columns if c != "value"]
    df = df.drop_duplicates(subset=key_cols, keep="first").reset_index(drop=True)
    df = _ensure_moderate_fallback(df)
    return df


def load_costs3():
    df = pd.read_excel(COSTS3_FILE)
    key_cols = ["scenario_id", "PEF", "nuts0_id", "year",
                "sector_id", "end_use_id", "energy_carrier_id"]
    df = df.drop_duplicates(subset=key_cols, keep="last").copy()
    # Rename scenario for consistency with paper
    df["scenario_id"] = df["scenario_id"].replace({"Pure economics": "Economics+"})
    return df


def _process_existing(df):
    """Map raw existing-file scenarios to clean names + PEF column."""
    # Normalise country labels and exclude Ukraine
    df = _normalise_country_names(df)
    # Filter to our countries and residential sector only
    df = df[df["nuts0_id"].isin(COUNTRIES)]
    df = df[df["sector_id"] == "Residential"].copy()
    # Map scenario and add PEF column
    df["_mapped"] = df["original_scenario_name"].map(_EXISTING_SCENARIO_MAP)
    df = df.dropna(subset=["_mapped"]).copy()
    df["scenario_id"] = df["_mapped"].apply(lambda x: x[0])
    df["PEF"] = df["_mapped"].apply(lambda x: x[1])
    df.drop(columns=["_mapped"], inplace=True)
    # Drop duplicates that arise when the same original scenario appears
    # multiple times mapped to the same paper label
    key_cols = [c for c in df.columns if c != "value"]
    df = df.drop_duplicates(subset=key_cols, keep="first").reset_index(drop=True)
    df = _ensure_moderate_fallback(df)
    return df


def load_target2_existing():
    """Hybrid loader for the existing-buildings file.

    Reads the new output_1_existing.xlsx (which has full Moderate runs for
    6 countries but is missing Sweden) plus the older target_indicators_2_
    existing.xlsx (which has Sweden for non-Moderate scenarios). For any
    country present in the new file, the new data wins; for any country
    missing from the new file (today, Sweden), data comes from the old
    file. Sweden's Moderate then falls back to Regulatory via the loader's
    moderate-fallback step. Once Sweden is added to output_1_existing.xlsx,
    the old file can be retired.
    """
    df_new = pd.read_excel(TARGET2_EXISTING_FILE)
    df_new = _normalise_country_names(df_new)
    new_countries = set(df_new["nuts0_id"].unique())

    fallback_path = DATA_DIR / "target_indicators_2_existing.xlsx"
    if fallback_path.exists():
        df_old = pd.read_excel(fallback_path)
        df_old = _normalise_country_names(df_old)
        # Take only countries missing from the new file
        df_old = df_old[~df_old["nuts0_id"].isin(new_countries)].copy()
        df_combined = pd.concat([df_new, df_old], ignore_index=True)
    else:
        df_combined = df_new

    df_combined = _process_existing(df_combined)
    df_combined.drop(columns=["original_scenario_name"],
                     errors="ignore", inplace=True)
    return df_combined



# =============================================================================
# Helper functions
# =============================================================================

def save_fig(fig, name, directory=None):
    out_dir = directory or FIGURE_DIR
    for ext in ("pdf", "png"):
        fig.savefig(out_dir / f"{name}.{ext}")
    plt.close(fig)
    print(f"  Saved {name}")


def _year_filter(df, years=None):
    if years is None:
        years = DISPLAY_YEARS
    return df[df["year"].isin(years)]


# =============================================================================
# Figure 1: FED Mix (stacked bar per country per PEF)
# =============================================================================

def fig1_fed_mix(df):
    print("Generating Fig 1: FED Mix...")
    fed = df[df["data_type_id"] == "FED"].copy()
    fed = _year_filter(fed)

    for country in COUNTRIES:
        for pef in PEF_TYPES:
            dc = fed[(fed["nuts0_id"] == country) & (fed["PEF"] == pef)]
            if dc.empty:
                continue

            fig, axes = plt.subplots(2, 3, figsize=(16, 9), sharey=True)
            # No suptitle — caption in LaTeX

            for idx, scenario in enumerate(SCENARIOS):
                ax = axes[idx // 3, idx % 3]
                ds = dc[dc["scenario_id"] == scenario]
                if ds.empty:
                    ax.set_title(scenario, fontsize=10)
                    ax.text(0.5, 0.5, "No data", ha="center", va="center",
                            transform=ax.transAxes, color="gray")
                    continue

                years = sorted(ds["year"].unique())
                x = np.arange(len(years))
                width = 0.6

                bottom = np.zeros(len(years))
                for carrier in CARRIER_ORDER:
                    for sector, hatch in [("Residential", ""), ("Tertiary", "///")]:
                        vals = []
                        for yr in years:
                            v = ds[(ds["year"] == yr) &
                                   (ds["energy_carrier_id"] == carrier) &
                                   (ds["sector_id"] == sector)]["value"].sum()
                            vals.append(v)
                        vals = np.array(vals)
                        if vals.sum() == 0:
                            continue
                        label = f"{carrier} ({sector[0]})" if hatch == "" else None
                        ax.bar(x, vals, width, bottom=bottom,
                               color=CARRIER_COLORS.get(carrier, "#cccccc"),
                               hatch=hatch, edgecolor="white", linewidth=0.3,
                               label=label if idx == 0 else None)
                        bottom += vals

                ax.set_title(scenario, fontsize=10)
                ax.set_xticks(x)
                ax.set_xticklabels(years, rotation=45, fontsize=7)
                if idx % 3 == 0:
                    ax.set_ylabel("FED [GWh/yr]")

            # Add top margin
            ymin, ymax = axes[0, 0].get_ylim()
            axes[0, 0].set_ylim(ymin, ymax * 1.05)

            # Shared legend
            handles, labels = axes[0, 0].get_legend_handles_labels()
            if handles:
                fig.legend(handles, labels, loc="lower center",
                           ncol=min(5, len(handles)), bbox_to_anchor=(0.5, -0.02),
                           fontsize=8)

            fig.tight_layout(rect=[0, 0.05, 1, 0.95])
            save_fig(fig, f"fig_fed_mix_{country.lower()}_{pef}")


# =============================================================================
# Figure 2: Total Primary Energy Demand (line chart)
# =============================================================================

def fig2_total_ped(df):
    print("Generating Fig 2: Total PED...")
    ped = df[df["data_type_id"] == "PED_incl_sf"].copy()
    ped = _year_filter(ped)

    # Sum over energy carriers and sectors
    ped_agg = (ped.groupby(["nuts0_id", "scenario_id", "PEF", "year"])["value"]
               .sum().reset_index())

    n_countries = len(COUNTRIES)
    fig, axes = plt.subplots(2, n_countries, figsize=(4 * n_countries, 8), sharey="row")
    for col, country in enumerate(COUNTRIES):
        for row, pef in enumerate(PEF_TYPES):
            ax = axes[row, col]
            dc = ped_agg[(ped_agg["nuts0_id"] == country) &
                         (ped_agg["PEF"] == pef)]

            for scenario in SCENARIOS:
                ds = dc[dc["scenario_id"] == scenario].sort_values("year")
                if ds.empty:
                    continue
                ax.plot(ds["year"], ds["value"],
                        color=SCENARIO_COLORS[scenario],
                        marker="o", markersize=3, linewidth=1.5,
                        label=scenario if col == 0 else None)

            ax.set_title(f"{country}" if row == 0 else "", fontsize=10)
            if col == 0:
                ax.set_ylabel(f"{pef} PEF\nPED [GWh/yr]")
            ax.set_xlim(2018, 2052)
            ax.tick_params(axis="x", rotation=45)

    # Add top margin to each row
    for row in range(2):
        ymin, ymax = axes[row, 0].get_ylim()
        axes[row, 0].set_ylim(ymin, ymax * 1.05)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(SCENARIOS),
               bbox_to_anchor=(0.5, -0.02), fontsize=9)
    fig.tight_layout(rect=[0, 0.04, 1, 0.95])
    save_fig(fig, "fig_total_ped_all_countries")


# =============================================================================
# Figure 2b: Total FED by energy carrier (Residential, 2020/2030/2035)
# =============================================================================

def fig2b_total_fed_carrier(df):
    """Total FED by individual energy carrier for residential sector.

    Layout: 7 rows (countries) x 4 columns (scenarios).
    Each panel shows 2020/2030/2035. Uses constant PEF only.
    Values in TWh/yr. Font: Lato Light (similar to Calibri Light).
    """
    print("Generating Fig 2b: Total FED carrier mix...")
    import matplotlib.transforms as mtransforms
    import matplotlib.font_manager as fm

    # Use Lato Light as substitute for Calibri Light
    lato_light = fm.FontProperties(family="Lato", weight=300)
    lato_bold = fm.FontProperties(family="Lato", weight=700)
    plt.rcParams.update({
        "font.family": "Lato",
        "font.weight": 300,
    })

    fed = df[(df["data_type_id"] == "FED") &
             (df["sector_id"] == "Residential") &
             (df["PEF"] == "constant")].copy()
    fed = _merge_res_carriers(fed)

    display_years = [2020, 2030, 2035]
    fed = fed[fed["year"].isin(display_years)]

    FED_CARRIER_ORDER = [
        "coal", "oil", "gas",
        "electricity",
        "district heating",
        "biomass", "ambient heat", "solar thermal",
        "pv space heating & dhw",
    ]
    # Fossil fuels in grey/black shadings; other carriers in distinct colours
    FED_CARRIER_COLORS = {
        "coal": "#2d2d2d",           # near black
        "oil": "#6b6b6b",            # medium grey
        "gas": "#a8a8a8",            # light grey
        "electricity": "#d64550",    # muted red
        "district heating": "#4a90c4",  # steel blue
        "biomass": "#5ba05b",        # forest green
        "ambient heat": "#e8a838",   # amber
        "solar thermal": "#e8c84a",  # golden yellow
        "pv space heating & dhw": "#d88ec2",  # dusty rose
    }
    FED_CARRIER_LABELS = {
        "coal": "Coal",
        "oil": "Oil",
        "gas": "Gas",
        "electricity": "Electricity",
        "district heating": "District heating",
        "biomass": "Biomass",
        "ambient heat": "Ambient heat",
        "solar thermal": "Solar thermal",
        "pv space heating & dhw": "PV space heating & DHW",
    }

    n_rows = len(COUNTRIES)
    n_cols = len(POLICY_SCENARIOS)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(11, 16),
                             sharey="row")
    for col, scenario in enumerate(POLICY_SCENARIOS):
        axes[0, col].set_title(scenario, fontsize=16,
                               fontproperties=lato_bold, pad=10)

    bar_width = 0.7

    for row, country in enumerate(COUNTRIES):
        for col, scenario in enumerate(POLICY_SCENARIOS):
            ax = axes[row, col]

            years_to_show = display_years

            for yi, yr in enumerate(years_to_show):
                dv = fed[(fed["nuts0_id"] == country) &
                         (fed["scenario_id"] == scenario) &
                         (fed["year"] == yr)]

                x_pos = yi * 1.1
                bottom = 0
                total = 0

                for carrier in FED_CARRIER_ORDER:
                    val = dv[dv["energy_carrier_id"] == carrier][
                        "value"].sum()
                    if val == 0:
                        continue
                    val_twh = val / 1000
                    ax.bar(x_pos, val_twh, bar_width,
                           bottom=bottom,
                           color=FED_CARRIER_COLORS[carrier],
                           edgecolor="white", linewidth=0.3,
                           zorder=2)
                    bottom += val_twh
                    total += val_twh

                # (no total annotation — y-axis gridlines suffice)

            # X-axis
            x_centers = [yi * 1.1 for yi in range(len(years_to_show))]
            ax.set_xticks(x_centers)
            ax.set_xticklabels([str(y) for y in years_to_show],
                               fontsize=11, fontproperties=lato_bold)
            ax.tick_params(axis="y", labelsize=10)
            for label in ax.get_yticklabels():
                label.set_fontproperties(lato_light)

            # Y-axis: unit only (country name placed separately)
            if col == 0:
                ax.set_ylabel("TWh/yr", fontsize=12,
                              fontproperties=lato_light)

            ax.grid(True, axis="y", alpha=0.2, linewidth=0.5)
            ax.grid(False, axis="x")
            n_bars = len(years_to_show)
            ax.set_xlim(-0.5, (n_bars - 1) * 1.1 + 0.7)

        # Country name as row label (left of first column)
        trans = mtransforms.blended_transform_factory(
            axes[row, 0].transAxes, axes[row, 0].transAxes)
        axes[row, 0].text(
            -0.5, 0.5, country, ha="center", va="center",
            fontsize=13, fontproperties=lato_bold, transform=trans,
            clip_on=False)

    # Slight top margin for breathing room
    for row in range(n_rows):
        ymin, ymax = axes[row, 0].get_ylim()
        axes[row, 0].set_ylim(0, ymax * 1.05)

    # Legend — two rows
    from matplotlib.patches import Patch
    legend_handles = [
        Patch(facecolor=FED_CARRIER_COLORS[c], edgecolor="white",
              label=FED_CARRIER_LABELS[c])
        for c in FED_CARRIER_ORDER]

    fig.legend(handles=legend_handles, loc="lower center",
               ncol=5, bbox_to_anchor=(0.54, -0.005), fontsize=11,
               frameon=True, edgecolor="lightgray", columnspacing=1.0,
               handletextpad=0.4, handlelength=1.5,
               prop=fm.FontProperties(family="Lato", weight=300, size=11))
    fig.tight_layout(rect=[0.07, 0.05, 1, 0.99])
    fig.subplots_adjust(hspace=0.30, wspace=0.15)
    save_fig(fig, "fig_total_fed_carrier")


# =============================================================================
# Figure 3: Specific (area-weighted) PED (line chart)
# =============================================================================

def fig3_specific_ped(df):
    print("Generating Fig 3: Specific PED (% reduction)...")
    sped = df[(df["data_type_id"] == "area-specific PED_incl_sf") &
              (df["sector_id"] == "Residential")].copy()
    sped = _year_filter(sped)

    # GFA data (Residential). At 2020 all scenarios share the same baseline,
    # so use Regulatory as the reference series for stock evolution.
    gfa = df[(df["data_type_id"] == "Heated gross floor area") &
             (df["sector_id"] == "Residential")].copy()
    gfa = _year_filter(gfa)
    gfa_agg = (gfa[gfa["scenario_id"] == "Regulatory"]
               .groupby(["nuts0_id", "PEF", "year"])["value"].sum().reset_index())

    # GFA 2020 baselines for percentage growth
    gfa_base = gfa_agg[gfa_agg["year"] == 2020].set_index(
        ["nuts0_id", "PEF"])["value"].to_dict()

    # Compute 2020 sPED baselines per country/PEF. All scenarios share the
    # 2020 value, so any scenario serves as reference. Use Regulatory.
    base = sped[(sped["year"] == 2020) & (sped["scenario_id"] == "Regulatory")]
    baselines = base.groupby(["nuts0_id", "PEF"])["value"].mean().to_dict()

    # Distinct line styles and markers per scenario (No policy excluded)
    SCENARIO_STYLES = {
        "Regulatory+":     {"ls": "-",  "marker": "o",  "lw": 2.0, "ms": 4},
        "Regulatory":      {"ls": "-",  "marker": "s",  "lw": 2.0, "ms": 4},
        "Moderate":        {"ls": "--", "marker": "^",  "lw": 1.5, "ms": 4},
        "Mix":             {"ls": "-",  "marker": "D",  "lw": 2.0, "ms": 3.5},
        "Economics+":  {"ls": "-.", "marker": "v",  "lw": 1.5, "ms": 4},
    }

    n_countries = len(COUNTRIES)
    # Transposed layout: rows = countries, columns = PEF types (portrait)
    fig, axes = plt.subplots(n_countries, 2, figsize=(11, n_countries * 2.4),
                             sharey="row")

    # Column titles
    for col_idx, pef_label in enumerate(["Constant PEF", "Decreasing PEF"]):
        axes[0, col_idx].set_title(pef_label, fontsize=13, fontweight="bold", pad=10)

    # White box style for target labels
    bbox_white = dict(boxstyle="round,pad=0.15", facecolor="white",
                      edgecolor="none", alpha=0.85)

    # Pre-compute PED and GFA ranges per column (PEF type) for aligned scaling
    ped_max_per_col = {0: 0, 1: 0}
    gfa_max_per_col = {0: 0, 1: 0}
    gfa_min_per_col = {0: 0, 1: 0}
    for row, country in enumerate(COUNTRIES):
        for col, pef in enumerate(PEF_TYPES):
            bl = baselines.get((country, pef), np.nan)
            dc = sped[(sped["nuts0_id"] == country) & (sped["PEF"] == pef)]
            for scenario in POLICY_SCENARIOS:
                ds = dc[dc["scenario_id"] == scenario]
                if ds.empty or np.isnan(bl) or bl == 0:
                    continue
                pct_red = (bl - ds["value"].values) / bl * 100
                ped_max_per_col[col] = max(ped_max_per_col[col],
                                           np.nanmax(pct_red))
            gfa_c = gfa_agg[(gfa_agg["nuts0_id"] == country) &
                            (gfa_agg["PEF"] == pef)]
            gfa_bl = gfa_base.get((country, pef), np.nan)
            if not gfa_c.empty and gfa_bl and gfa_bl > 0:
                gfa_pct = (gfa_c["value"].values - gfa_bl) / gfa_bl * 100
                gfa_max_per_col[col] = max(gfa_max_per_col[col],
                                           np.nanmax(gfa_pct))
                gfa_min_per_col[col] = min(gfa_min_per_col[col],
                                           np.nanmin(gfa_pct))

    for row, country in enumerate(COUNTRIES):
        for col, pef in enumerate(PEF_TYPES):
            ax = axes[row, col]
            dc = sped[(sped["nuts0_id"] == country) & (sped["PEF"] == pef)]
            bl = baselines.get((country, pef), np.nan)

            # Compute aligned axis limits
            ped_top = ped_max_per_col[col] * 1.10
            ped_bottom = -2

            ped_range = ped_top - ped_bottom
            f_zero = (0 - ped_bottom) / ped_range
            gfa_max_val = max(gfa_max_per_col[col] * 1.15, 5)
            gfa_range = gfa_max_val / max(0.40 - f_zero, 0.1)
            gfa_bottom = -f_zero * gfa_range
            gfa_top = gfa_bottom + gfa_range

            # GFA first (behind everything)
            ax2 = ax.twinx()
            gfa_c = gfa_agg[(gfa_agg["nuts0_id"] == country) &
                            (gfa_agg["PEF"] == pef)].sort_values("year")
            gfa_bl = gfa_base.get((country, pef), np.nan)
            if not gfa_c.empty and gfa_bl and gfa_bl > 0:
                gfa_pct = (gfa_c["value"].values - gfa_bl) / gfa_bl * 100
                ax2.fill_between(gfa_c["year"].values, 0, gfa_pct,
                                 color="#e8e4d8", alpha=0.35, zorder=0)
                ax2.plot(gfa_c["year"].values, gfa_pct,
                         color="#a09070", linewidth=1.0, zorder=1)
            ax2.set_ylim(gfa_bottom, gfa_top)
            # GFA axis ticks on right column only
            if col == 1:
                ax2.set_ylabel("GFA change [%]", fontsize=9,
                               color="#666666")
                ax2.tick_params(axis="y", labelsize=8, colors="#666666")
            else:
                ax2.set_yticklabels([])
                ax2.tick_params(axis="y", length=0)

            # Vertical highlight bands at target years
            ax.axvspan(2029, 2031, color="#fee0d2", alpha=0.5, zorder=1)
            ax.axvspan(2034, 2036, color="#deebf7", alpha=0.5, zorder=1)

            # Scenario lines (policy scenarios only)
            for scenario in POLICY_SCENARIOS:
                ds = dc[dc["scenario_id"] == scenario].sort_values("year")
                if ds.empty or np.isnan(bl) or bl == 0:
                    continue
                pct_reduction = (bl - ds["value"].values) / bl * 100
                sty = SCENARIO_STYLES[scenario]
                ax.plot(ds["year"].values, pct_reduction,
                        color=SCENARIO_COLORS[scenario],
                        linestyle=sty["ls"], linewidth=sty["lw"],
                        label=scenario if row == 0 and col == 0 else None,
                        zorder=3)

                # Markers only at 2030 and 2035
                for tyr in [2030, 2035]:
                    mask = ds["year"].values == tyr
                    if mask.any():
                        ax.plot(ds["year"].values[mask],
                                pct_reduction[mask],
                                marker=sty["marker"], markersize=sty["ms"],
                                color=SCENARIO_COLORS[scenario],
                                markeredgewidth=0.6, markeredgecolor="black",
                                linestyle="none", zorder=5)

            # EPBD 2030 target
            ax.plot([2028, 2032], [16, 16], color="#b22222",
                    linestyle="--", linewidth=1.5, zorder=4)
            # EPBD 2035 target band
            ax.fill_between([2033, 2037], 20, 22, color="#b22222",
                            alpha=0.18, zorder=4, linewidth=0)
            ax.plot([2033, 2037], [20, 20], color="#b22222",
                    linestyle="--", linewidth=0.8, zorder=4)
            ax.plot([2033, 2037], [22, 22], color="#b22222",
                    linestyle="--", linewidth=0.8, zorder=4)

            # Target labels
            ax.text(2032.5, 16, "16%", fontsize=8, color="#b22222",
                    fontweight="bold", ha="left", va="bottom",
                    bbox=bbox_white, zorder=6)
            ax.text(2037.5, 21, "20\u201322%", fontsize=8, color="#b22222",
                    fontweight="bold", ha="left", va="center",
                    bbox=bbox_white, zorder=6)

            # Country labels on left column
            if col == 0:
                ax.set_ylabel(country, fontsize=11, fontweight="bold")
            else:
                ax.set_ylabel("")

            # X-axis labels only on bottom row
            ax.set_xlim(2018, 2052)
            ax.set_xticks(DISPLAY_YEARS)
            if row == n_countries - 1:
                ax.set_xticklabels([str(y) for y in DISPLAY_YEARS],
                                   rotation=45, ha="right", fontsize=9)
            else:
                ax.set_xticklabels([])

            ax.tick_params(axis="y", labelsize=9)
            ax.set_ylim(ped_bottom, ped_top)

            # Clean grid
            ax.grid(True, axis="y", alpha=0.2, linewidth=0.5)
            ax.grid(False, axis="x")

    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    handles, labels = axes[0, 0].get_legend_handles_labels()
    handles.append(Patch(facecolor="#e8e4d8", alpha=0.5, edgecolor="#a09070",
                         linewidth=1.0, label="GFA change"))
    labels.append("GFA change")
    handles.append(Line2D([0], [0], color="#b22222", linestyle="--",
                          linewidth=1.5, label="EPBD target"))
    labels.append("EPBD target")
    fig.legend(handles, labels, loc="lower center",
               ncol=len(POLICY_SCENARIOS) + 2,
               bbox_to_anchor=(0.5, -0.01), fontsize=10, frameon=True,
               edgecolor="lightgray", fancybox=True, shadow=False,
               columnspacing=1.5, handlelength=2.5)
    fig.tight_layout(rect=[0.0, 0.03, 1, 0.98])
    fig.subplots_adjust(hspace=0.12, wspace=0.15)
    save_fig(fig, "fig_specific_ped_residential")


# =============================================================================
# Figure 3-GFA: Gross Floor Area evolution (dedicated figure)
# =============================================================================

def fig3_gfa(df):
    """Dedicated GFA figure showing heated gross floor area evolution by scenario."""
    print("Generating Fig 3-GFA: Gross Floor Area...")
    gfa = df[(df["data_type_id"] == "Heated gross floor area") &
             (df["sector_id"] == "Residential")].copy()
    gfa = _year_filter(gfa)

    # Aggregate over energy carriers
    gfa_agg = (gfa.groupby(["nuts0_id", "scenario_id", "PEF", "year"])["value"]
               .sum().reset_index())

    # 2020 baselines (No policy)
    base = gfa_agg[(gfa_agg["year"] == 2020) & (gfa_agg["scenario_id"] == "No policy")]
    baselines = base.groupby(["nuts0_id", "PEF"])["value"].mean().to_dict()

    n_countries = len(COUNTRIES)
    fig, axes = plt.subplots(2, n_countries, figsize=(4.4 * n_countries, 9),
                             sharey="row")

    fig.text(0.005, 0.72, "Constant PEF", va="center", ha="left",
             fontsize=14, fontweight="bold", rotation=90)
    fig.text(0.005, 0.30, "Decreasing PEF", va="center", ha="left",
             fontsize=14, fontweight="bold", rotation=90)

    for col, country in enumerate(COUNTRIES):
        for row, pef in enumerate(PEF_TYPES):
            ax = axes[row, col]
            dc = gfa_agg[(gfa_agg["nuts0_id"] == country) &
                         (gfa_agg["PEF"] == pef)]
            bl = baselines.get((country, pef), np.nan)

            for scenario in SCENARIOS:
                ds = dc[dc["scenario_id"] == scenario].sort_values("year")
                if ds.empty or np.isnan(bl) or bl == 0:
                    continue
                pct_change = (ds["value"].values - bl) / bl * 100
                ax.plot(ds["year"].values, pct_change,
                        color=SCENARIO_COLORS[scenario],
                        marker="o", markersize=3, linewidth=1.5,
                        label=scenario if col == 0 and row == 0 else None)

            ax.axhline(y=0, color="black", linewidth=0.5, linestyle="-",
                       alpha=0.3)

            if row == 0:
                ax.set_title(country, fontsize=14, fontweight="bold", pad=8)
            if col == 0:
                ax.set_ylabel("GFA change vs 2020 [%]", fontsize=12)

            ax.set_xlim(2018, 2052)
            ax.set_xticks(DISPLAY_YEARS)
            ax.set_xticklabels([str(y) for y in DISPLAY_YEARS],
                               rotation=45, ha="right", fontsize=10)
            ax.tick_params(axis="y", labelsize=10)
            ax.grid(True, axis="y", alpha=0.2, linewidth=0.5)
            ax.grid(False, axis="x")

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(SCENARIOS),
               bbox_to_anchor=(0.5, -0.02), fontsize=10, frameon=True,
               edgecolor="lightgray")
    fig.tight_layout(rect=[0.02, 0.05, 1, 0.96])
    fig.subplots_adjust(hspace=0.25, wspace=0.15)
    save_fig(fig, "fig_target_indicators_gfa")


# =============================================================================
# Figure 3b: Specific PED carrier mix (stacked bar, both PEF side by side)
# =============================================================================

def _merge_res_carriers(ped_df):
    """Merge 'from RES' variants into their parent carriers."""
    res_map = {
        "oil from RES": "oil",
        "gas from RES": "gas",
        "electricity from RES": "electricity",
        "district heating from RES": "district heating",
    }
    df = ped_df.copy()
    df["energy_carrier_id"] = df["energy_carrier_id"].replace(res_map)
    return df


# Merged carrier order and colors (no "from RES" entries)
CARRIER_ORDER_MERGED = [
    "coal", "oil", "gas",
    "electricity",
    "district heating",
    "biomass", "ambient heat", "solar thermal", "pv space heating & dhw",
]

CARRIER_COLORS_MERGED = {
    "coal": "#2d2d2d",
    "oil": "#8c510a",
    "gas": "#bf812d",
    "electricity": "#c0392b",
    "district heating": "#1a5276",
    "biomass": "#27ae60",
    "ambient heat": "#76d7c4",
    "solar thermal": "#f4d03f",
    "pv space heating & dhw": "#a3e048",
}


def fig3b_specific_ped_carrier(df):
    print("Generating Fig 3b: Specific PED carrier mix...")
    # PED_incl_sf has carrier breakdown; divide by GFA for area-specific
    ped = df[(df["data_type_id"] == "PED_incl_sf") &
             (df["sector_id"] == "Residential")].copy()
    gfa = df[(df["data_type_id"] == "Heated gross floor area") &
             (df["sector_id"] == "Residential")].copy()

    display_years = [2020, 2030, 2050]
    ped = ped[ped["year"].isin(display_years)]
    gfa = gfa[gfa["year"].isin(display_years)]

    # Merge "from RES" into parent carriers
    ped = _merge_res_carriers(ped)

    # Total GFA per country/scenario/PEF/year
    gfa_totals = (gfa.groupby(["nuts0_id", "scenario_id", "PEF", "year"])
                  ["value"].sum().to_dict())

    n_rows = len(COUNTRIES)
    n_cols = len(POLICY_SCENARIOS)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, 20),
                             sharey="row")


    # Column titles (scenarios)
    for col, scenario in enumerate(POLICY_SCENARIOS):
        axes[0, col].set_title(scenario, fontsize=14, fontweight="bold", pad=8)

    for row, country in enumerate(COUNTRIES):
        for col, scenario in enumerate(POLICY_SCENARIOS):
            ax = axes[row, col]
            ds = ped[(ped["nuts0_id"] == country) &
                     (ped["scenario_id"] == scenario)]

            years = display_years
            n_years = len(years)
            bar_width = 0.35
            gap = 0.05

            for yi, yr in enumerate(years):
                for pi, pef in enumerate(PEF_TYPES):
                    dv = ds[(ds["year"] == yr) & (ds["PEF"] == pef)]
                    gfa_val = gfa_totals.get(
                        (country, scenario, pef, yr), np.nan)
                    x_pos = yi * (2 * bar_width + gap + 0.3) + \
                        pi * (bar_width + gap)
                    bottom = 0
                    for carrier in CARRIER_ORDER_MERGED:
                        val = dv[dv["energy_carrier_id"] == carrier][
                            "value"].sum()
                        if val == 0 or np.isnan(gfa_val) or gfa_val == 0:
                            continue
                        val_specific = val / gfa_val
                        hatch = "" if pi == 0 else "///"
                        ax.bar(x_pos, val_specific, bar_width, bottom=bottom,
                               color=CARRIER_COLORS_MERGED.get(carrier, "#cccccc"),
                               hatch=hatch, edgecolor="white", linewidth=0.3,
                               zorder=2)
                        bottom += val_specific

            # X-axis: year labels centered between the two bars
            x_centers = [yi * (2 * bar_width + gap + 0.3)
                         + (bar_width + gap) / 2
                         for yi in range(n_years)]
            ax.set_xticks(x_centers)
            ax.set_xticklabels([str(y) for y in years], fontsize=13)
            ax.tick_params(axis="y", labelsize=13)

            # Row label (country) on first column
            if col == 0:
                ax.set_ylabel(f"{country}\nkWh/(m$^2$ yr)", fontsize=14,
                              fontweight="bold")

            ax.grid(True, axis="y", alpha=0.2, linewidth=0.5)
            ax.grid(False, axis="x")

    # Build legend
    from matplotlib.patches import Patch
    legend_handles = []
    for carrier in CARRIER_ORDER_MERGED:
        legend_handles.append(Patch(facecolor=CARRIER_COLORS_MERGED[carrier],
                                    edgecolor="white",
                                    label=carrier.title()))
    legend_handles.append(Patch(facecolor="gray", edgecolor="white",
                                label="Constant PEF (left)"))
    legend_handles.append(Patch(facecolor="gray", edgecolor="white",
                                hatch="///",
                                label="Decreasing PEF (right)"))

    fig.legend(handles=legend_handles, loc="lower center",
               ncol=min(6, len(legend_handles)),
               bbox_to_anchor=(0.5, -0.01), fontsize=13, frameon=True,
               edgecolor="lightgray")
    fig.tight_layout(rect=[0, 0.04, 1, 0.96])
    fig.subplots_adjust(hspace=0.15, wspace=0.15)
    save_fig(fig, "fig_specific_ped_carrier_both_pef_v5")


# =============================================================================
# Figure 3b-scaled: Specific PED carrier mix — scaled to match direct totals
# =============================================================================

def fig3b_specific_ped_carrier_scaled(df):
    print("Generating Fig 3b-scaled: Specific PED carrier mix (scaled)...")
    ped = df[(df["data_type_id"] == "PED_incl_sf") &
             (df["sector_id"] == "Residential")].copy()
    gfa = df[(df["data_type_id"] == "Heated gross floor area") &
             (df["sector_id"] == "Residential")].copy()
    # Direct area-specific totals (the trusted reference)
    area_spec = df[(df["data_type_id"] == "area-specific PED_incl_sf") &
                   (df["sector_id"] == "Residential")].copy()

    display_years = [2020, 2030, 2050]
    ped = ped[ped["year"].isin(display_years)]
    gfa = gfa[gfa["year"].isin(display_years)]
    area_spec = area_spec[area_spec["year"].isin(display_years)]

    # Merge "from RES" into parent carriers
    ped = _merge_res_carriers(ped)

    gfa_totals = (gfa.groupby(["nuts0_id", "scenario_id", "PEF", "year"])
                  ["value"].sum().to_dict())
    # Direct area-specific totals
    direct_totals = (area_spec.groupby(
        ["nuts0_id", "scenario_id", "PEF", "year"])["value"]
        .mean().to_dict())

    n_rows = len(COUNTRIES)
    n_cols = len(POLICY_SCENARIOS)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, 20),
                             sharey="row")


    for col, scenario in enumerate(POLICY_SCENARIOS):
        axes[0, col].set_title(scenario, fontsize=14, fontweight="bold",
                               pad=8)

    for row, country in enumerate(COUNTRIES):
        for col, scenario in enumerate(POLICY_SCENARIOS):
            ax = axes[row, col]
            ds = ped[(ped["nuts0_id"] == country) &
                     (ped["scenario_id"] == scenario)]

            n_years = len(display_years)
            bar_width = 0.35
            gap = 0.05

            for yi, yr in enumerate(display_years):
                for pi, pef in enumerate(PEF_TYPES):
                    dv = ds[(ds["year"] == yr) & (ds["PEF"] == pef)]
                    gfa_val = gfa_totals.get(
                        (country, scenario, pef, yr), np.nan)
                    direct_val = direct_totals.get(
                        (country, scenario, pef, yr), np.nan)

                    if np.isnan(gfa_val) or gfa_val == 0:
                        continue

                    # Compute raw carrier shares
                    carrier_vals = {}
                    raw_total = 0
                    for carrier in CARRIER_ORDER_MERGED:
                        val = dv[dv["energy_carrier_id"] == carrier][
                            "value"].sum()
                        if val > 0:
                            specific = val / gfa_val
                            carrier_vals[carrier] = specific
                            raw_total += specific

                    # Scale to match direct total
                    if raw_total > 0 and not np.isnan(direct_val):
                        scale = direct_val / raw_total
                    else:
                        scale = 1.0

                    x_pos = yi * (2 * bar_width + gap + 0.3) + \
                        pi * (bar_width + gap)
                    bottom = 0
                    for carrier in CARRIER_ORDER_MERGED:
                        if carrier not in carrier_vals:
                            continue
                        val_scaled = carrier_vals[carrier] * scale
                        hatch = "" if pi == 0 else "///"
                        ax.bar(x_pos, val_scaled, bar_width,
                               bottom=bottom,
                               color=CARRIER_COLORS_MERGED.get(
                                   carrier, "#cccccc"),
                               hatch=hatch, edgecolor="white",
                               linewidth=0.3, zorder=2)
                        bottom += val_scaled

            x_centers = [yi * (2 * bar_width + gap + 0.3)
                         + (bar_width + gap) / 2
                         for yi in range(n_years)]
            ax.set_xticks(x_centers)
            ax.set_xticklabels([str(y) for y in display_years],
                               fontsize=13)
            ax.tick_params(axis="y", labelsize=13)

            if col == 0:
                ax.set_ylabel(f"{country}\nkWh/(m$^2$ yr)", fontsize=14,
                              fontweight="bold")

            ax.grid(True, axis="y", alpha=0.2, linewidth=0.5)
            ax.grid(False, axis="x")

    # Add top margin to each row
    for row in range(n_rows):
        ymin, ymax = axes[row, 0].get_ylim()
        axes[row, 0].set_ylim(ymin, ymax * 1.05)

    from matplotlib.patches import Patch
    legend_handles = []
    for carrier in CARRIER_ORDER_MERGED:
        legend_handles.append(Patch(facecolor=CARRIER_COLORS_MERGED[carrier],
                                    edgecolor="white",
                                    label=carrier.title()))
    legend_handles.append(Patch(facecolor="gray", edgecolor="white",
                                label="Constant PEF (left)"))
    legend_handles.append(Patch(facecolor="gray", edgecolor="white",
                                hatch="///",
                                label="Decreasing PEF (right)"))

    fig.legend(handles=legend_handles, loc="lower center",
               ncol=min(6, len(legend_handles)),
               bbox_to_anchor=(0.5, -0.01), fontsize=13, frameon=True,
               edgecolor="lightgray")
    fig.tight_layout(rect=[0, 0.04, 1, 0.96])
    fig.subplots_adjust(hspace=0.15, wspace=0.15)
    save_fig(fig, "fig_specific_ped_carrier_scaled")


# =============================================================================
# Figure 3c: Specific PED carrier mix — GROUPED categories
# =============================================================================

def fig3c_specific_ped_carrier_grouped(df):
    print("Generating Fig 3c: Specific PED carrier mix (grouped)...")
    ped = df[(df["data_type_id"] == "PED_incl_sf") &
             (df["sector_id"] == "Residential")].copy()
    gfa = df[(df["data_type_id"] == "Heated gross floor area") &
             (df["sector_id"] == "Residential")].copy()

    display_years = [2020, 2030, 2035]
    ped = ped[ped["year"].isin(display_years)]
    gfa = gfa[gfa["year"].isin(display_years)]

    gfa_totals = (gfa.groupby(["nuts0_id", "scenario_id", "PEF", "year"])
                  ["value"].sum().to_dict())

    # Grouped carrier categories (incl. "from RES" variants)
    CARRIER_GROUPS = {
        "Fossil (coal, oil, gas,\nincl. from RES)":
            ["coal", "oil", "gas", "oil from RES", "gas from RES"],
        "Electricity\n(incl. from RES)":
            ["electricity", "electricity from RES"],
        "District heating\n(incl. from RES)":
            ["district heating", "district heating from RES"],
        "Renewables (biomass, ambient\nheat, solar thermal, PV)":
            ["biomass", "ambient heat", "solar thermal",
             "pv space heating & dhw"],
    }

    GROUP_COLORS = {
        "Fossil (coal, oil, gas,\nincl. from RES)": "#8c510a",
        "Electricity\n(incl. from RES)": "#e08214",
        "District heating\n(incl. from RES)": "#2166ac",
        "Renewables (biomass, ambient\nheat, solar thermal, PV)": "#1b7837",
    }
    GROUP_ORDER = list(CARRIER_GROUPS.keys())

    n_rows = len(COUNTRIES)
    n_cols = len(POLICY_SCENARIOS)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(20, 22),
                             sharey="row")


    for col, scenario in enumerate(POLICY_SCENARIOS):
        axes[0, col].set_title(scenario, fontsize=13, fontweight="bold",
                               pad=10)

    for row, country in enumerate(COUNTRIES):
        for col, scenario in enumerate(POLICY_SCENARIOS):
            ax = axes[row, col]
            ds = ped[(ped["nuts0_id"] == country) &
                     (ped["scenario_id"] == scenario)]

            n_years = len(display_years)
            bar_width = 0.38
            gap = 0.06

            for yi, yr in enumerate(display_years):
                for pi, pef in enumerate(PEF_TYPES):
                    dv = ds[(ds["year"] == yr) & (ds["PEF"] == pef)]
                    gfa_val = gfa_totals.get(
                        (country, scenario, pef, yr), np.nan)
                    x_pos = yi * (2 * bar_width + gap + 0.35) + \
                        pi * (bar_width + gap)
                    bottom = 0

                    for group_name in GROUP_ORDER:
                        carriers = CARRIER_GROUPS[group_name]
                        val = dv[dv["energy_carrier_id"].isin(carriers)][
                            "value"].sum()
                        if val == 0 or np.isnan(gfa_val) or gfa_val == 0:
                            continue
                        val_specific = val / gfa_val
                        hatch = "" if pi == 0 else "////"
                        ax.bar(x_pos, val_specific, bar_width,
                               bottom=bottom,
                               color=GROUP_COLORS[group_name],
                               hatch=hatch, edgecolor="white",
                               linewidth=0.4, zorder=2)
                        bottom += val_specific

            # X-axis
            x_centers = [yi * (2 * bar_width + gap + 0.35)
                         + (bar_width + gap) / 2
                         for yi in range(n_years)]
            ax.set_xticks(x_centers)
            ax.set_xticklabels([str(y) for y in display_years],
                               fontsize=13)
            ax.tick_params(axis="y", labelsize=13)

            if col == 0:
                ax.set_ylabel(f"{country}\nkWh/(m$^2$ yr)", fontsize=14,
                              fontweight="bold")

            ax.grid(True, axis="y", alpha=0.2, linewidth=0.5)
            ax.grid(False, axis="x")

    # Add top margin to each row
    for row in range(n_rows):
        ymin, ymax = axes[row, 0].get_ylim()
        axes[row, 0].set_ylim(ymin, ymax * 1.05)

    # Legend
    from matplotlib.patches import Patch
    legend_handles = []
    for group_name in GROUP_ORDER:
        legend_handles.append(
            Patch(facecolor=GROUP_COLORS[group_name], edgecolor="white",
                  label=group_name))
    legend_handles.append(
        Patch(facecolor="#888888", edgecolor="white",
              label="Constant PEF (left bar)"))
    legend_handles.append(
        Patch(facecolor="#888888", edgecolor="white", hatch="////",
              label="Decreasing PEF (right bar)"))

    fig.legend(handles=legend_handles, loc="lower center",
               ncol=3, bbox_to_anchor=(0.5, -0.01), fontsize=14,
               frameon=True, edgecolor="lightgray", columnspacing=2,
               handletextpad=0.8, handlelength=2.5)
    fig.tight_layout(rect=[0, 0.05, 1, 0.96])
    fig.subplots_adjust(hspace=0.15, wspace=0.15)
    save_fig(fig, "fig_specific_ped_carrier_grouped")


# =============================================================================
# Figure 4: Primary Energy Savings vs PEF — 2030 (grouped bar)
# =============================================================================

def fig4_pe_savings_vs_pef(df):
    print("Generating Fig 4: PE Savings vs PEF (2030)...")
    sped = df[(df["data_type_id"] == "area-specific PED_incl_sf") &
              (df["sector_id"] == "Residential")].copy()

    # Get 2020 baselines (No policy)
    base = sped[(sped["year"] == 2020) & (sped["scenario_id"] == "No policy")]
    baselines = base.groupby(["nuts0_id", "PEF"])["value"].mean().to_dict()

    # Get 2030 values for policy scenarios
    vals_2030 = sped[(sped["year"] == 2030) &
                     (sped["scenario_id"].isin(POLICY_SCENARIOS))]

    n_countries = len(COUNTRIES)
    fig, axes = plt.subplots(1, n_countries, figsize=(3.6 * n_countries, 5), sharey=True)


    bar_width = 0.35
    x = np.arange(len(POLICY_SCENARIOS))

    for col, country in enumerate(COUNTRIES):
        ax = axes[col]
        for i, pef in enumerate(PEF_TYPES):
            savings = []
            for scenario in POLICY_SCENARIOS:
                bl = baselines.get((country, pef), np.nan)
                v = vals_2030[(vals_2030["nuts0_id"] == country) &
                              (vals_2030["PEF"] == pef) &
                              (vals_2030["scenario_id"] == scenario)]["value"].mean()
                if bl and bl > 0:
                    savings.append((bl - v) / bl * 100)
                else:
                    savings.append(0)

            offset = (i - 0.5) * bar_width
            ax.bar(x + offset, savings, bar_width,
                   color=PEF_BAR_COLORS[pef],
                   label=f"{pef} PEF" if col == 0 else None)

        ax.axhline(y=16, color="red", linestyle="--", linewidth=1, alpha=0.7)
        ax.text(len(POLICY_SCENARIOS) - 0.5, 16.5, "EPBD 16%",
                fontsize=7, color="red", ha="right")

        ax.set_title(country, fontsize=10)
        ax.set_xticks(x)
        ax.set_xticklabels(POLICY_SCENARIOS, rotation=45, ha="right", fontsize=7)
        if col == 0:
            ax.set_ylabel("PE savings [%]")

    # Add top margin
    ymin, ymax = axes[0].get_ylim()
    axes[0].set_ylim(ymin, ymax * 1.08)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2,
               bbox_to_anchor=(0.5, -0.02), fontsize=9)
    fig.tight_layout(rect=[0, 0.05, 1, 0.95])
    save_fig(fig, "fig_pe_savings_2030_vs_pef")


# =============================================================================
# Figure 5: Target Achievements (consolidated dot plot)
# =============================================================================

def fig5_target_achievements(df):
    print("Generating Fig 5: Target Achievements...")
    sped = df[(df["data_type_id"] == "area-specific PED_incl_sf") &
              (df["sector_id"] == "Residential")].copy()

    # 2020 baselines
    base = sped[(sped["year"] == 2020) & (sped["scenario_id"] == "No policy")]
    baselines = base.groupby(["nuts0_id", "PEF"])["value"].mean().to_dict()

    target_years = {"2030": 2030, "2035": 2035}

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    # No suptitle — caption in LaTeX

    for panel_idx, (label, yr) in enumerate(target_years.items()):
        ax = axes[panel_idx]
        vals = sped[(sped["year"] == yr) &
                    (sped["scenario_id"].isin(POLICY_SCENARIOS))]

        y_positions = np.arange(len(COUNTRIES))
        x_positions = np.arange(len(POLICY_SCENARIOS))

        for j, scenario in enumerate(POLICY_SCENARIOS):
            for k, pef in enumerate(PEF_TYPES):
                marker = "o" if pef == "constant" else "s"
                savings_list = []
                for i, country in enumerate(COUNTRIES):
                    bl = baselines.get((country, pef), np.nan)
                    v = vals[(vals["nuts0_id"] == country) &
                             (vals["PEF"] == pef) &
                             (vals["scenario_id"] == scenario)]["value"].mean()
                    if bl and bl > 0:
                        sav = (bl - v) / bl * 100
                    else:
                        sav = 0
                    savings_list.append(sav)

                colors = []
                target_pct = 16 if yr == 2030 else 20
                for sav in savings_list:
                    colors.append("#2ca02c" if sav >= target_pct else "#d62728")

                x_offset = j + (k - 0.5) * 0.25
                ax.scatter([x_offset] * len(COUNTRIES), y_positions,
                           c=colors, marker=marker, s=80, edgecolors="black",
                           linewidths=0.5, zorder=3,
                           label=f"{pef} PEF" if (j == 0 and panel_idx == 0) else None)

                # Add value labels
                for i, sav in enumerate(savings_list):
                    ax.annotate(f"{sav:.0f}%", (x_offset, y_positions[i]),
                                textcoords="offset points", xytext=(0, 8),
                                ha="center", fontsize=6)

        ax.set_title(f"{label} (target: {16 if yr == 2030 else 20}%)", fontsize=11)
        ax.set_xticks(np.arange(len(POLICY_SCENARIOS)))
        ax.set_xticklabels(POLICY_SCENARIOS, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(y_positions)
        ax.set_yticklabels(COUNTRIES)
        ax.axvline(x=-0.5, color="gray", linewidth=0.5)
        for j in range(len(POLICY_SCENARIOS)):
            ax.axvline(x=j + 0.5, color="gray", linewidth=0.3, alpha=0.5)

    # Legend for marker shapes
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="gray",
               markersize=8, label="constant PEF"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="gray",
               markersize=8, label="decreasing PEF"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#2ca02c",
               markersize=8, label="Target met"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#d62728",
               markersize=8, label="Target not met"),
    ]
    fig.legend(handles=legend_elements, loc="lower center", ncol=4,
               bbox_to_anchor=(0.5, -0.02), fontsize=9)
    fig.tight_layout(rect=[0, 0.05, 1, 0.95])
    save_fig(fig, "fig_target_achievement_consolidated")


# =============================================================================
# Figure 6: Costs (grouped/stacked bar)
# =============================================================================

def fig6_costs(df_costs):
    print("Generating Fig 6: Costs...")
    # Sum over energy_carrier_id and sector_id, keep end_use_id split
    cost_agg = (df_costs.groupby(["nuts0_id", "scenario_id", "PEF",
                                   "year", "end_use_id"])["value"]
                .sum().reset_index())

    end_uses = ["Envelope thermal refurbishment share excl. subsidies",
                "Space heating & DHW System & PV excl. subsidies"]
    end_use_labels = ["Envelope", "Heating system & PV"]
    end_use_colors = ["#1f77b4", "#ff7f0e"]

    # Use constant PEF and year 2050 as primary view; show all scenarios
    for pef in PEF_TYPES:
        n_countries = len(COUNTRIES)
        fig, axes = plt.subplots(1, n_countries, figsize=(3.6 * n_countries, 5), sharey=True)


        bar_width = 0.5
        for col, country in enumerate(COUNTRIES):
            ax = axes[col]
            dc = cost_agg[(cost_agg["nuts0_id"] == country) &
                          (cost_agg["PEF"] == pef)]

            # Group by scenario and year
            scenarios_in_data = [s for s in SCENARIOS if s in dc["scenario_id"].values]
            years_in_data = sorted(dc["year"].unique())

            n_years = len(years_in_data)
            n_scenarios = len(scenarios_in_data)
            group_width = n_years * bar_width + 0.3
            x = np.arange(n_scenarios) * group_width

            for yi, yr in enumerate(years_in_data):
                bottom = np.zeros(n_scenarios)
                for eu_idx, (eu, eu_label) in enumerate(zip(end_uses, end_use_labels)):
                    vals = []
                    for scenario in scenarios_in_data:
                        v = dc[(dc["scenario_id"] == scenario) &
                               (dc["year"] == yr) &
                               (dc["end_use_id"] == eu)]["value"].sum()
                        vals.append(v)
                    vals = np.array(vals)

                    ax.bar(x + yi * bar_width, vals, bar_width,
                           bottom=bottom, color=end_use_colors[eu_idx],
                           edgecolor="white", linewidth=0.3,
                           label=f"{eu_label} ({yr})" if col == 0 else None)
                    bottom += vals

            ax.set_title(country, fontsize=10)
            ax.set_xticks(x + (n_years - 1) * bar_width / 2)
            ax.set_xticklabels(scenarios_in_data, rotation=45, ha="right", fontsize=7)
            if col == 0:
                ax.set_ylabel("Investment [MEUR/yr]")

        # Add top margin
        ymin, ymax = axes[0].get_ylim()
        axes[0].set_ylim(ymin, ymax * 1.05)

        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="lower center",
                   ncol=min(6, len(handles)),
                   bbox_to_anchor=(0.5, -0.04), fontsize=8)
        fig.tight_layout(rect=[0, 0.06, 1, 0.95])
        save_fig(fig, f"fig_costs_all_countries_{pef}")


# =============================================================================
# Figure 7: Waterfall — drivers of sPED change (Art 9(2) target decomposition)
# =============================================================================

def _get_carrier_sfed_pef(fed_df, ped_df, country, scenario, pef_type,
                          year, eff_gfa):
    """Compute sFED and PEF per carrier for a given filter."""
    ambient_solar = ["ambient heat", "solar thermal", "pv space heating & dhw"]
    non_ambient = ["coal", "oil", "gas", "biomass", "electricity",
                   "district heating"]
    f = fed_df[(fed_df["nuts0_id"] == country) &
               (fed_df["scenario_id"] == scenario) &
               (fed_df["PEF"] == pef_type) & (fed_df["year"] == year)]
    p = ped_df[(ped_df["nuts0_id"] == country) &
               (ped_df["scenario_id"] == scenario) &
               (ped_df["PEF"] == pef_type) & (ped_df["year"] == year)]
    result = {}
    for c in non_ambient + ambient_solar:
        fed_val = f[f["energy_carrier_id"] == c]["value"].sum()
        ped_val = p[p["energy_carrier_id"] == c]["value"].sum()
        sfed = fed_val / eff_gfa if eff_gfa > 0 else 0
        pef = ped_val / fed_val if fed_val > 0 else 0
        result[c] = {"sfed": sfed, "pef": pef}
    return result


def _waterfall_decompose(df_all, df_existing, country, scenario, pef_type,
                         yr_base, yr_target):
    """Decompose sPED change into new construction, FED savings,
    ambient/solar, and PEF effect.

    Returns (sped_start, bars, sped_end) where bars is a list of
    (label, value) tuples. Positive value = PED reduction (bar goes down).
    """
    ambient_solar = ["ambient heat", "solar thermal", "pv space heating & dhw"]
    non_ambient = ["coal", "oil", "gas", "biomass", "electricity",
                   "district heating"]

    # --- ALL buildings data ---
    fed_all = df_all[(df_all["data_type_id"] == "FED") &
                     (df_all["sector_id"] == "Residential")].copy()
    ped_all = df_all[(df_all["data_type_id"] == "PED_incl_sf") &
                     (df_all["sector_id"] == "Residential")].copy()
    sped_ref_all = df_all[
        (df_all["data_type_id"] == "area-specific PED_incl_sf") &
        (df_all["sector_id"] == "Residential")].copy()
    fed_all = _merge_res_carriers(fed_all)
    ped_all = _merge_res_carriers(ped_all)

    # --- EXISTING buildings data ---
    fed_ex = df_existing[(df_existing["data_type_id"] == "FED") &
                         (df_existing["sector_id"] == "Residential")].copy()
    ped_ex = df_existing[(df_existing["data_type_id"] == "PED_incl_sf") &
                         (df_existing["sector_id"] == "Residential")].copy()
    sped_ref_ex = df_existing[
        (df_existing["data_type_id"] == "area-specific PED_incl_sf") &
        (df_existing["sector_id"] == "Residential")].copy()
    fed_ex = _merge_res_carriers(fed_ex)
    ped_ex = _merge_res_carriers(ped_ex)

    def filt_sped(d, y):
        return d[(d["nuts0_id"] == country) &
                 (d["scenario_id"] == scenario) &
                 (d["PEF"] == pef_type) & (d["year"] == y)]

    # Trusted area-specific PED values
    sped_all_0 = filt_sped(sped_ref_all, yr_base)["value"].mean()
    sped_all_t = filt_sped(sped_ref_all, yr_target)["value"].mean()
    sped_ex_t = filt_sped(sped_ref_ex, yr_target)["value"].mean()
    # 2020: all buildings = existing buildings
    sped_ex_0 = filt_sped(sped_ref_ex, yr_base)["value"].mean()

    if any(np.isnan(v) for v in [sped_all_0, sped_all_t]) or sped_all_0 == 0:
        return sped_all_0, [], sped_all_t

    # If existing data not available for this scenario, fall back to 3 bars
    has_existing = not np.isnan(sped_ex_t) and not np.isnan(sped_ex_0)

    # Verify 2020 identity: all buildings = existing buildings
    if has_existing and abs(sped_all_0 - sped_ex_0) > 0.5:
        print(f"    WARNING: sPED mismatch in 2020 for {country}/{scenario}/"
              f"{pef_type}: all={sped_all_0:.1f}, ex={sped_ex_0:.1f}")

    # Effective GFA for existing buildings
    ped_ex_total_0 = filt_sped(ped_ex, yr_base)["value"].sum()
    ped_ex_total_t = filt_sped(ped_ex, yr_target)["value"].sum()

    if has_existing and sped_ex_0 > 0 and sped_ex_t > 0:
        eff_gfa_ex_0 = ped_ex_total_0 / sped_ex_0
        eff_gfa_ex_t = ped_ex_total_t / sped_ex_t
    else:
        has_existing = False

    if has_existing:
        # Full 5-bar decomposition with new construction
        # Bar 1: New construction effect
        bar_new = sped_ex_t - sped_all_t

        # Bars 2-4: decompose EXISTING stock change
        d_ex_0 = _get_carrier_sfed_pef(
            fed_ex, ped_ex, country, scenario, pef_type,
            yr_base, eff_gfa_ex_0)
        d_ex_t = _get_carrier_sfed_pef(
            fed_ex, ped_ex, country, scenario, pef_type,
            yr_target, eff_gfa_ex_t)

        # Use PEFs from existing data (same grid PEFs apply)
        sfed_ex_total_0 = sum(
            d_ex_0[c]["sfed"] for c in non_ambient + ambient_solar)
        sfed_ex_total_t = sum(
            d_ex_t[c]["sfed"] for c in non_ambient + ambient_solar)
        bar_fed = sfed_ex_total_0 - sfed_ex_total_t

        sfed_ex_amb_0 = sum(d_ex_0[c]["sfed"] for c in ambient_solar)
        sfed_ex_amb_t = sum(d_ex_t[c]["sfed"] for c in ambient_solar)
        bar_amb = sfed_ex_amb_t - sfed_ex_amb_0

        bar_pef = sum(
            d_ex_0[c]["sfed"] * (d_ex_0[c]["pef"] - 1) -
            d_ex_t[c]["sfed"] * (d_ex_t[c]["pef"] - 1)
            for c in non_ambient
        )

        bars = [
            ("New\nconstruction", bar_new),
            ("FED\nsavings", bar_fed),
            ("Ambient &\nsolar", bar_amb),
            ("PEF\neffect", bar_pef),
        ]
    else:
        # Fallback: 3-bar decomposition using all-buildings data
        ped_all_total_0 = filt_sped(ped_all, yr_base)["value"].sum()
        ped_all_total_t = filt_sped(ped_all, yr_target)["value"].sum()
        eff_gfa_0 = ped_all_total_0 / sped_all_0
        eff_gfa_t = ped_all_total_t / sped_all_t

        d0 = _get_carrier_sfed_pef(
            fed_all, ped_all, country, scenario, pef_type,
            yr_base, eff_gfa_0)
        dt = _get_carrier_sfed_pef(
            fed_all, ped_all, country, scenario, pef_type,
            yr_target, eff_gfa_t)

        sfed_total_0 = sum(d0[c]["sfed"] for c in non_ambient + ambient_solar)
        sfed_total_t = sum(dt[c]["sfed"] for c in non_ambient + ambient_solar)
        bar_fed = sfed_total_0 - sfed_total_t

        sfed_amb_0 = sum(d0[c]["sfed"] for c in ambient_solar)
        sfed_amb_t = sum(dt[c]["sfed"] for c in ambient_solar)
        bar_amb = sfed_amb_t - sfed_amb_0

        bar_pef = sum(
            d0[c]["sfed"] * (d0[c]["pef"] - 1) -
            dt[c]["sfed"] * (dt[c]["pef"] - 1)
            for c in non_ambient
        )

        bars = [
            ("FED\nsavings", bar_fed),
            ("Ambient &\nsolar", bar_amb),
            ("PEF\neffect", bar_pef),
        ]

    return sped_all_0, bars, sped_all_t


def _draw_waterfall(ax, sped_0, bars, sped_t, yr_target, driver_colors,
                    start_end_color, connector_color):
    """Draw a single waterfall chart on the given axes.

    Value labels are placed BELOW each bar. X-axis uses short
    abbreviations: 2020, New, FED, Amb, PEF, {year}.
    """
    short_label = {
        "New\nconstruction": "New",
        "FED\nsavings": "FED",
        "Ambient &\nsolar": "Amb",
        "PEF\neffect": "PEF",
    }
    labels = ["2020"] + \
             [short_label.get(b[0], b[0]) for b in bars] + \
             [str(yr_target)]
    n_bars = len(labels)
    x = np.arange(n_bars)
    bar_w = 0.52

    bottoms = []
    heights = []
    colors = []

    # Start bar (full from 0)
    bottoms.append(0)
    heights.append(sped_0)
    colors.append(start_end_color)

    running = sped_0
    for label, val in bars:
        if val >= 0:
            bottoms.append(running - val)
            heights.append(val)
        else:
            bottoms.append(running)
            heights.append(-val)
        colors.append(driver_colors.get(label, "#999999"))
        running = running - val

    # End bar (full from 0)
    bottoms.append(0)
    heights.append(sped_t)
    colors.append(start_end_color)

    # Draw bars
    for i in range(n_bars):
        ax.bar(x[i], heights[i], bar_w, bottom=bottoms[i],
               color=colors[i], edgecolor="none", linewidth=0, zorder=3)

    # Connector lines
    running = sped_0
    for i, (label, val) in enumerate(bars):
        y_connect = running
        ax.plot([x[i] + bar_w / 2, x[i + 1] - bar_w / 2],
                [y_connect, y_connect], color=connector_color,
                linewidth=0.7, linestyle=":", zorder=2)
        running = running - val
    ax.plot([x[-2] + bar_w / 2, x[-1] - bar_w / 2],
            [running, running], color=connector_color,
            linewidth=0.7, linestyle=":", zorder=2)

    # --- Value labels: BELOW each bar ---
    label_fs = 8
    y_offset = sped_0 * 0.025  # gap below the bar

    # Start bar: value below
    ax.text(x[0], -y_offset, f"{sped_0:.0f}",
            ha="center", va="top",
            fontsize=label_fs, fontweight="bold", zorder=5)

    # End bar: value below
    ax.text(x[-1], -y_offset, f"{sped_t:.0f}",
            ha="center", va="top",
            fontsize=label_fs, fontweight="bold", zorder=5)

    # Driver bars: value below each bar
    for i, (label, val) in enumerate(bars):
        sign = "\u2212" if val >= 0 else "+"
        txt = f"{sign}{abs(val):.0f}"
        bar_bot = bottoms[i + 1]
        ax.text(x[i + 1], bar_bot - y_offset, txt,
                ha="center", va="top",
                fontsize=label_fs, fontweight="bold",
                color=colors[i + 1], zorder=5)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, rotation=0, ha="center")


def _draw_waterfall_relative(ax, sped_0, bars, sped_t, yr_target,
                             driver_colors, start_end_color, connector_color):
    """Draw a single waterfall chart normalized to 100% (2020 baseline).

    All values expressed as % of sPED 2020.
    """
    short_label = {
        "New\nconstruction": "New",
        "FED\nsavings": "FED",
        "Ambient &\nsolar": "Amb",
        "PEF\neffect": "PEF",
    }
    labels = ["2020"] + \
             [short_label.get(b[0], b[0]) for b in bars] + \
             [str(yr_target)]
    n_bars = len(labels)
    x = np.arange(n_bars)
    bar_w = 0.52

    # Normalize everything to percentage of sped_0
    scale = 100.0 / sped_0 if sped_0 > 0 else 1.0
    sped_0_pct = 100.0
    sped_t_pct = sped_t * scale
    bars_pct = [(lbl, val * scale) for lbl, val in bars]

    bottoms = []
    heights = []
    colors = []

    # Start bar (full from 0)
    bottoms.append(0)
    heights.append(sped_0_pct)
    colors.append(start_end_color)

    running = sped_0_pct
    for label, val in bars_pct:
        if val >= 0:
            bottoms.append(running - val)
            heights.append(val)
        else:
            bottoms.append(running)
            heights.append(-val)
        colors.append(driver_colors.get(label, "#999999"))
        running = running - val

    # End bar (full from 0)
    bottoms.append(0)
    heights.append(sped_t_pct)
    colors.append(start_end_color)

    # Draw bars
    for i in range(n_bars):
        ax.bar(x[i], heights[i], bar_w, bottom=bottoms[i],
               color=colors[i], edgecolor="none", linewidth=0, zorder=3)

    # Connector lines
    running = sped_0_pct
    for i, (label, val) in enumerate(bars_pct):
        y_connect = running
        ax.plot([x[i] + bar_w / 2, x[i + 1] - bar_w / 2],
                [y_connect, y_connect], color=connector_color,
                linewidth=0.7, linestyle=":", zorder=2)
        running = running - val
    ax.plot([x[-2] + bar_w / 2, x[-1] - bar_w / 2],
            [running, running], color=connector_color,
            linewidth=0.7, linestyle=":", zorder=2)

    # --- Value labels: BELOW each bar ---
    label_fs = 8
    y_offset = 2.5  # gap below the bar in %

    # Start bar: value below
    ax.text(x[0], -y_offset, "100%",
            ha="center", va="top",
            fontsize=label_fs, fontweight="bold", zorder=5)

    # End bar: value below
    ax.text(x[-1], -y_offset, f"{sped_t_pct:.0f}%",
            ha="center", va="top",
            fontsize=label_fs, fontweight="bold", zorder=5)

    # Driver bars: value below each bar
    for i, (label, val) in enumerate(bars_pct):
        sign = "\u2212" if val >= 0 else "+"
        txt = f"{sign}{abs(val):.0f}%"
        bar_bot = bottoms[i + 1]
        ax.text(x[i + 1], bar_bot - y_offset, txt,
                ha="center", va="top",
                fontsize=label_fs, fontweight="bold",
                color=colors[i + 1], zorder=5)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, rotation=0, ha="center")


def fig7_waterfall(df_all, df_existing):
    """Waterfall diagram: drivers of specific PED change from 2020.

    Full decomposition: Start -> New construction -> FED savings (existing) ->
    Ambient/solar (existing) -> PEF effect (existing) -> End.
    """
    print("Generating Fig 7: Waterfall decomposition...")

    driver_colors = {
        "New\nconstruction": "#756bb1",
        "FED\nsavings": "#3182bd",
        "Ambient &\nsolar": "#2ca02c",
        "PEF\neffect": "#e6550d",
    }
    start_end_color = "#333333"
    connector_color = "#999999"

    from matplotlib.patches import Patch
    n_countries = len(COUNTRIES)
    panel_labels = [f"({chr(97+i)})" for i in range(n_countries)]

    for pef_type in PEF_TYPES:
        for yr_target in [2030, 2035, 2050]:
            for scenario in POLICY_SCENARIOS:
                fig, axes = plt.subplots(1, n_countries, figsize=(2 * n_countries, 3.5),
                                         sharey=True)

                # Track which driver labels actually appear
                used_drivers = set()

                # First pass: compute decompositions and find global max
                decompositions = []
                max_sped = 0
                for country in COUNTRIES:
                    sped_0, bars, sped_t = _waterfall_decompose(
                        df_all, df_existing, country, scenario,
                        pef_type, 2020, yr_target)
                    decompositions.append((sped_0, bars, sped_t))
                    if not np.isnan(sped_0):
                        max_sped = max(max_sped, sped_0)

                # Second pass: draw all panels
                for col, country in enumerate(COUNTRIES):
                    ax = axes[col]
                    sped_0, bars, sped_t = decompositions[col]

                    if not bars:
                        ax.text(0.5, 0.5, "No data",
                                transform=ax.transAxes, ha="center",
                                fontsize=9)
                        ax.set_title(
                            f"{panel_labels[col]} {country}",
                            fontsize=10, fontweight="bold")
                        continue

                    for lbl, _ in bars:
                        used_drivers.add(lbl)

                    _draw_waterfall(ax, sped_0, bars, sped_t, yr_target,
                                    driver_colors, start_end_color,
                                    connector_color)
                    ax.set_title(
                        f"{panel_labels[col]} {country}",
                        fontsize=10, fontweight="bold")
                    if col == 0:
                        ax.set_ylabel(
                            r"kWh/(m$^2$ yr)", fontsize=9)
                    ax.tick_params(axis="y", labelsize=8)

                # Set shared y-axis limits: room below for labels
                if max_sped > 0:
                    axes[0].set_ylim(bottom=-max_sped * 0.08,
                                     top=max_sped * 1.05)

                # Legend — only show drivers that actually appear
                legend_handles = [
                    Patch(facecolor=start_end_color, edgecolor="white",
                          label="Start / End (sPED)"),
                ]
                for lbl, clr in driver_colors.items():
                    if lbl in used_drivers:
                        legend_handles.append(
                            Patch(facecolor=clr, edgecolor="white",
                                  label=lbl.replace("\n", " ")))
                fig.legend(handles=legend_handles, loc="lower center",
                           ncol=len(legend_handles),
                           bbox_to_anchor=(0.5, -0.02), fontsize=8,
                           frameon=True, edgecolor="lightgray")
                fig.tight_layout(rect=[0, 0.10, 1, 1.0])
                scen_slug = scenario.lower().replace(
                    " ", "_").replace("+", "plus")
                save_fig(fig,
                         f"fig_waterfall_{yr_target}_{pef_type}_{scen_slug}",
                         directory=WATERFALL_DIR)


# =============================================================================
# Figure 7b: Relative waterfall — normalized to 100% of 2020 baseline
# =============================================================================

def fig7b_waterfall_relative(df_all, df_existing):
    """Waterfall diagram normalized to 100% of sPED 2020 baseline."""
    print("Generating Fig 7b: Relative waterfall (normalized to 100%)...")

    driver_colors = {
        "New\nconstruction": "#756bb1",
        "FED\nsavings": "#3182bd",
        "Ambient &\nsolar": "#2ca02c",
        "PEF\neffect": "#e6550d",
    }
    start_end_color = "#333333"
    connector_color = "#999999"

    from matplotlib.patches import Patch
    n_countries = len(COUNTRIES)
    panel_labels = [f"({chr(97+i)})" for i in range(n_countries)]

    for pef_type in PEF_TYPES:
        for yr_target in [2030, 2035, 2050]:
            for scenario in POLICY_SCENARIOS:
                fig, axes = plt.subplots(1, n_countries, figsize=(2 * n_countries, 3.5),
                                         sharey=True)

                used_drivers = set()
                decompositions = []
                for country in COUNTRIES:
                    sped_0, bars, sped_t = _waterfall_decompose(
                        df_all, df_existing, country, scenario,
                        pef_type, 2020, yr_target)
                    decompositions.append((sped_0, bars, sped_t))

                for col, country in enumerate(COUNTRIES):
                    ax = axes[col]
                    sped_0, bars, sped_t = decompositions[col]

                    if not bars:
                        ax.text(0.5, 0.5, "No data",
                                transform=ax.transAxes, ha="center",
                                fontsize=9)
                        ax.set_title(
                            f"{panel_labels[col]} {country}",
                            fontsize=10, fontweight="bold")
                        continue

                    for lbl, _ in bars:
                        used_drivers.add(lbl)

                    _draw_waterfall_relative(
                        ax, sped_0, bars, sped_t, yr_target,
                        driver_colors, start_end_color, connector_color)
                    ax.set_title(
                        f"{panel_labels[col]} {country}",
                        fontsize=10, fontweight="bold")
                    if col == 0:
                        ax.set_ylabel("% of sPED 2020", fontsize=9)
                    ax.tick_params(axis="y", labelsize=8)

                # Y limits: 0-based percentage with room for labels below
                axes[0].set_ylim(bottom=-8, top=110)

                legend_handles = [
                    Patch(facecolor=start_end_color, edgecolor="white",
                          label="Start / End (sPED)"),
                ]
                for lbl, clr in driver_colors.items():
                    if lbl in used_drivers:
                        legend_handles.append(
                            Patch(facecolor=clr, edgecolor="white",
                                  label=lbl.replace("\n", " ")))
                fig.legend(handles=legend_handles, loc="lower center",
                           ncol=len(legend_handles),
                           bbox_to_anchor=(0.5, -0.02), fontsize=8,
                           frameon=True, edgecolor="lightgray")
                fig.tight_layout(rect=[0, 0.10, 1, 1.0])
                scen_slug = scenario.lower().replace(
                    " ", "_").replace("+", "plus")
                save_fig(
                    fig,
                    f"fig_waterfall_rel_{yr_target}_{pef_type}_{scen_slug}",
                    directory=WATERFALL_DIR)


# =============================================================================
# Figure 7c: Combined PEF waterfall — constant + decreasing side by side
# =============================================================================

def fig7c_waterfall_combined_pef(df_all, df_existing):
    """Waterfall with constant and decreasing PEF side by side per country."""
    print("Generating Fig 7c: Combined PEF waterfall...")

    driver_colors = {
        "New\nconstruction": "#756bb1",
        "FED\nsavings": "#3182bd",
        "Ambient &\nsolar": "#2ca02c",
        "PEF\neffect": "#e6550d",
    }
    start_end_color = "#333333"
    connector_color = "#999999"

    from matplotlib.patches import Patch

    short_label = {
        "New\nconstruction": "New",
        "FED\nsavings": "FED",
        "Ambient &\nsolar": "Amb",
        "PEF\neffect": "PEF",
    }

    n_countries = len(COUNTRIES)
    for yr_target in [2030, 2035, 2050]:
        for scenario in POLICY_SCENARIOS:
            fig, axes = plt.subplots(2, n_countries, figsize=(2.4 * n_countries, 7), sharey=True)

            # Row labels
            fig.text(0.005, 0.72, "Constant PEF", va="center", ha="left",
                     fontsize=11, fontweight="bold", rotation=90)
            fig.text(0.005, 0.28, "Decreasing PEF", va="center", ha="left",
                     fontsize=11, fontweight="bold", rotation=90)

            used_drivers = set()
            max_sped = 0

            # Precompute all decompositions
            all_decomp = {}
            for pef_type in PEF_TYPES:
                for country in COUNTRIES:
                    sped_0, bars, sped_t = _waterfall_decompose(
                        df_all, df_existing, country, scenario,
                        pef_type, 2020, yr_target)
                    all_decomp[(pef_type, country)] = (sped_0, bars, sped_t)
                    if not np.isnan(sped_0):
                        max_sped = max(max_sped, sped_0)

            panel_labels = [f"({chr(97+i)})" for i in range(n_countries)]

            for row, pef_type in enumerate(PEF_TYPES):
                for col, country in enumerate(COUNTRIES):
                    ax = axes[row, col]
                    sped_0, bars, sped_t = all_decomp[(pef_type, country)]

                    if not bars:
                        ax.text(0.5, 0.5, "No data",
                                transform=ax.transAxes, ha="center",
                                fontsize=9)
                        if row == 0:
                            ax.set_title(country, fontsize=10,
                                         fontweight="bold")
                        continue

                    for lbl, _ in bars:
                        used_drivers.add(lbl)

                    _draw_waterfall(ax, sped_0, bars, sped_t, yr_target,
                                    driver_colors, start_end_color,
                                    connector_color)
                    if row == 0:
                        ax.set_title(country, fontsize=10, fontweight="bold")
                    if col == 0:
                        ax.set_ylabel(
                            r"kWh/(m$^2$ yr)", fontsize=9)
                    ax.tick_params(axis="y", labelsize=8)

            if max_sped > 0:
                axes[0, 0].set_ylim(bottom=-max_sped * 0.08,
                                    top=max_sped * 1.05)

            legend_handles = [
                Patch(facecolor=start_end_color, edgecolor="white",
                      label="Start / End (sPED)"),
            ]
            for lbl, clr in driver_colors.items():
                if lbl in used_drivers:
                    legend_handles.append(
                        Patch(facecolor=clr, edgecolor="white",
                              label=lbl.replace("\n", " ")))
            fig.legend(handles=legend_handles, loc="lower center",
                       ncol=len(legend_handles),
                       bbox_to_anchor=(0.5, -0.01), fontsize=8,
                       frameon=True, edgecolor="lightgray")
            fig.tight_layout(rect=[0.02, 0.06, 1, 1.0])
            fig.subplots_adjust(hspace=0.25)
            scen_slug = scenario.lower().replace(
                " ", "_").replace("+", "plus")
            save_fig(fig,
                     f"fig_waterfall_combined_{yr_target}_{scen_slug}",
                     directory=WATERFALL_DIR)


# =============================================================================
# Figure 8: Waterfall summary — all scenarios in one panel per country
# =============================================================================

def fig8_waterfall_summary(df_all, df_existing):
    """Waterfall summary: all scenarios side by side, one panel per country.

    Stacked bars decompose sPED change from 2020 to target year.
    Bottom (dark) = sPED target year. Colored segments = drivers.
    Solid dark bar at top = sPED 2020 baseline.
    """
    print("Generating Fig 8: Waterfall summary (all scenarios)...")

    driver_colors = {
        "New\nconstruction": "#756bb1",
        "FED\nsavings": "#3182bd",
        "Ambient &\nsolar": "#2ca02c",
        "PEF\neffect": "#e6550d",
    }
    start_end_color = "#333333"
    baseline_color = "#555555"

    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D

    for pef_type in PEF_TYPES:
        for yr_target in [2030, 2050]:
            n_countries = len(COUNTRIES)
            fig, axes = plt.subplots(1, n_countries, figsize=(3.6 * n_countries, 5.5), sharey=True)
            # No suptitle — caption in LaTeX

            # Compute all decompositions and find global max
            all_decomp = {}
            max_sped = 0
            for country in COUNTRIES:
                for scenario in POLICY_SCENARIOS:
                    sped_0, bars, sped_t = _waterfall_decompose(
                        df_all, df_existing, country, scenario,
                        pef_type, 2020, yr_target)
                    all_decomp[(country, scenario)] = (sped_0, bars, sped_t)
                    if not np.isnan(sped_0):
                        max_sped = max(max_sped, sped_0)

            used_drivers = set()

            for col, country in enumerate(COUNTRIES):
                ax = axes[col]
                n_scen = len(POLICY_SCENARIOS)
                x = np.arange(n_scen)
                bar_w = 0.65

                sped_0_val = None

                for i, scenario in enumerate(POLICY_SCENARIOS):
                    sped_0, bars, sped_t = all_decomp[
                        (country, scenario)]
                    if not bars or np.isnan(sped_0):
                        continue
                    sped_0_val = sped_0

                    for lbl, _ in bars:
                        used_drivers.add(lbl)

                    # --- sPED 2020: solid dark bar at the top ---
                    # Draw thin dark band at sPED_2020 level
                    band_h = max_sped * 0.025
                    ax.bar(x[i], band_h, bar_w, bottom=sped_0 - band_h,
                           color=start_end_color, edgecolor="none",
                           zorder=5)

                    # --- sPED target year: dark bar from 0 ---
                    ax.bar(x[i], sped_t, bar_w, bottom=0,
                           color=start_end_color, edgecolor="none",
                           zorder=2)
                    # Value label on dark bar
                    ax.text(x[i], sped_t * 0.5, f"{sped_t:.0f}",
                            ha="center", va="center", fontsize=7,
                            fontweight="bold", color="white", zorder=6)

                    # --- Stack driver segments upward from sPED_target ---
                    # Reverse order so PEF at bottom, New constr. at top
                    running = sped_t
                    for label, val in reversed(bars):
                        clr = driver_colors.get(label, "#999999")
                        if abs(val) < 0.3:
                            running += val
                            continue
                        ax.bar(x[i], val, bar_w, bottom=running,
                               color=clr, edgecolor="white",
                               linewidth=0.4, zorder=3)

                        # Value label
                        seg_h = abs(val)
                        mid_y = running + val / 2
                        sign = "\u2212" if val >= 0 else "+"
                        txt = f"{sign}{abs(val):.0f}"
                        if seg_h > 10:
                            ax.text(x[i], mid_y, txt,
                                    ha="center", va="center",
                                    fontsize=6.5, fontweight="bold",
                                    color="white", zorder=6)
                        else:
                            ax.text(x[i] + bar_w / 2 + 0.06, mid_y,
                                    txt, ha="left", va="center",
                                    fontsize=5.5, fontweight="bold",
                                    color=clr, zorder=6)

                        running += val

                # sPED 2020 label
                if sped_0_val is not None:
                    ax.text(n_scen - 0.7, sped_0_val + max_sped * 0.015,
                            f"sPED 2020: {sped_0_val:.0f}",
                            ha="right", va="bottom", fontsize=8,
                            fontweight="bold", color=start_end_color,
                            zorder=7)

                ax.set_title(country, fontsize=11, fontweight="bold")
                # Short scenario labels for x-axis
                short_scen = {
                    "Regulatory+": "Reg+",
                    "Regulatory": "Reg",
                    "Moderate": "Mod",
                    "Mix": "Mix",
                    "Economics+": "Econ",
                }
                ax.set_xticks(x)
                ax.set_xticklabels(
                    [short_scen.get(s, s) for s in POLICY_SCENARIOS],
                    rotation=0, ha="center", fontsize=8)
                if col == 0:
                    ax.set_ylabel(r"kWh/(m$^2$ yr)")
                ax.grid(True, axis="y", alpha=0.2, linewidth=0.5)
                ax.grid(False, axis="x")

            # Set y limits with margin
            axes[0].set_ylim(0, max_sped * 1.15)

            # Legend
            legend_handles = [
                Patch(facecolor=start_end_color, edgecolor="white",
                      label="sPED 2020 / sPED " + str(yr_target)),
            ]
            for lbl in ["New\nconstruction", "FED\nsavings",
                        "Ambient &\nsolar", "PEF\neffect"]:
                if lbl in used_drivers:
                    legend_handles.append(
                        Patch(facecolor=driver_colors[lbl],
                              edgecolor="white",
                              label=lbl.replace("\n", " ")))

            fig.legend(handles=legend_handles, loc="lower center",
                       ncol=len(legend_handles),
                       bbox_to_anchor=(0.5, -0.02), fontsize=9,
                       frameon=True, edgecolor="lightgray")
            fig.tight_layout(rect=[0, 0.06, 1, 0.95])
            save_fig(fig, f"fig_waterfall_summary_{yr_target}_{pef_type}",
                     directory=WATERFALL_DIR)


def fig9_waterfall_horizontal(df_all, df_existing):
    """Horizontal bar waterfall: all countries side by side.

    Layout: 2 rows (constant / decreasing PEF) x 7 columns (countries).
    Each cell has 4 horizontal bars (scenarios), decomposing sPED change.
    Uses Lato font (similar to Calibri Light) and a muted color palette.
    """
    print("Generating Fig 9: Horizontal waterfall bars...")

    import matplotlib
    from matplotlib.patches import Patch
    from matplotlib.ticker import MaxNLocator

    # --- Font: Lato (light weight, similar to Calibri Light) ---
    _fp = {"family": "Lato", "weight": 300}
    _fb = {"family": "Lato", "weight": 600}
    matplotlib.rcParams.update({"font.family": "Lato", "font.weight": 300})

    # --- Muted, colorblind-friendly palette ---
    driver_colors = {
        "New\nconstruction": "#009E73",   # bluish green (Okabe-Ito)
        "FED\nsavings": "#56B4E9",        # sky blue (Okabe-Ito)
        "Ambient &\nsolar": "#E69F00",    # orange (Okabe-Ito)
        "PEF\neffect": "#CC79A7",         # reddish purple (Okabe-Ito)
    }
    start_end_color = "#2C3E50"

    driver_order = ["PEF\neffect", "Ambient &\nsolar",
                    "FED\nsavings", "New\nconstruction"]

    scen_order = ["Regulatory+", "Regulatory", "Moderate", "Economics+"]
    short_scen = {"Regulatory+": "Reg+", "Regulatory": "Reg",
                  "Moderate": "Mod", "Economics+": "Econ"}

    for yr_target in [2030, 2035, 2050]:
        n_c = len(COUNTRIES)
        fig, axes = plt.subplots(
            2, n_c, figsize=(n_c * 3.2, 7.4),
            sharey=False, sharex=False)


        # Precompute all decompositions
        all_decomp = {}
        for country in COUNTRIES:
            for pef_type in PEF_TYPES:
                for scenario in scen_order:
                    sped_0, bars, sped_t = _waterfall_decompose(
                        df_all, df_existing, country, scenario,
                        pef_type, 2020, yr_target)
                    all_decomp[(country, pef_type, scenario)] = (
                        sped_0, bars, sped_t)

        used_drivers = set()

        for row, pef_type in enumerate(PEF_TYPES):
            for col, country in enumerate(COUNTRIES):
                ax = axes[row, col]
                y_pos = np.arange(len(scen_order))
                bar_h = 0.58

                # Per-country x-range: find min target and max extent
                col_min = 999
                col_max = 0
                for scenario in scen_order:
                    s0, bb, st = all_decomp[(country, pef_type, scenario)]
                    if bb and not np.isnan(s0):
                        col_min = min(col_min, st)
                        ext = st + sum(abs(v) for _, v in bb)
                        col_max = max(col_max, s0, ext)
                x_lo = max(0, col_min - 20)
                x_hi = col_max * 1.05

                sped_0_ref = None

                for i, scenario in enumerate(scen_order):
                    sped_0, bars, sped_t = all_decomp[
                        (country, pef_type, scenario)]
                    if not bars or np.isnan(sped_0):
                        continue
                    if sped_0_ref is None:
                        sped_0_ref = sped_0

                    # Dark bar: sPED at target year
                    ax.barh(y_pos[i], sped_t - x_lo, bar_h, left=x_lo,
                            color=start_end_color, edgecolor="none",
                            zorder=3)
                    # Value label always centered in dark bar
                    bar_mid = x_lo + (sped_t - x_lo) / 2
                    fs = 9.5 if (sped_t - x_lo) > 20 else 8.5
                    ax.text(bar_mid, y_pos[i], f"{sped_t:.0f}",
                            ha="center", va="center", fontsize=fs,
                            color="white", zorder=5, **_fb)

                    bar_dict = {lbl: val for lbl, val in bars}

                    # Stack driver segments rightward
                    running = sped_t
                    # Find last visible worsening segment
                    visible_segs = [(drv, bar_dict.get(drv, 0))
                                    for drv in driver_order
                                    if abs(bar_dict.get(drv, 0)) >= 0.3]
                    last_worsening_drv = None
                    for drv, v in reversed(visible_segs):
                        if v < 0:
                            last_worsening_drv = drv
                            break

                    for drv in driver_order:
                        val = bar_dict.get(drv, 0)
                        if abs(val) < 0.3:
                            continue
                        used_drivers.add(drv)
                        clr = driver_colors[drv]
                        worsening = val < 0
                        ax.barh(y_pos[i], val, bar_h, left=running,
                                color=clr,
                                edgecolor="#222222" if worsening
                                    else "white",
                                linewidth=1.5 if worsening else 0.4,
                                hatch="//////" if worsening else "",
                                zorder=3)

                        # Value label: "+" if worsening, "−" if reducing
                        txt = (f"+{abs(val):.0f}" if worsening
                               else f"\u2212{abs(val):.0f}")
                        mid_x = running + val / 2
                        is_last_w = (drv == last_worsening_drv)
                        if abs(val) > 14:
                            ax.text(mid_x, y_pos[i], txt,
                                    ha="center", va="center",
                                    fontsize=9, color="#1a1a1a",
                                    zorder=5, **_fb)
                        elif abs(val) >= 7:
                            ax.text(mid_x, y_pos[i], txt,
                                    ha="center", va="center",
                                    fontsize=8, color="#1a1a1a",
                                    zorder=5, **_fb)
                        elif worsening and is_last_w and abs(val) < 7:
                            # Last + segment: label to the right
                            right_x = running + abs(val) + 0.5
                            ax.text(right_x, y_pos[i], txt,
                                    ha="left", va="center",
                                    fontsize=7, color="#1a1a1a",
                                    zorder=5, **_fb)
                        elif abs(val) >= 4:
                            ax.text(mid_x, y_pos[i] - bar_h / 2 - 0.08,
                                    txt, ha="center", va="bottom",
                                    fontsize=7, color="#444444",
                                    zorder=5, **_fp)
                        elif abs(val) >= 2:
                            ax.text(mid_x, y_pos[i] - bar_h / 2 - 0.08,
                                    txt, ha="center", va="bottom",
                                    fontsize=6, color="#444444",
                                    zorder=5, **_fp)

                        running += val

                # 2020 baseline: dashed vertical line
                if sped_0_ref is not None and not np.isnan(sped_0_ref):
                    ax.axvline(sped_0_ref, color="#444444", linewidth=1.8,
                               linestyle="--", dashes=(5, 3),
                               zorder=2, alpha=1.0)

                ax.set_xlim(x_lo, x_hi)
                ax.grid(True, axis="x", alpha=0.12, linewidth=0.4)
                ax.grid(False, axis="y")
                ax.invert_yaxis()
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)

                # Column title: country name + 2020 baseline (top row)
                if row == 0:
                    ax.set_title(country, fontsize=13, pad=18, **_fb)
                    if sped_0_ref is not None and not np.isnan(sped_0_ref):
                        ax.text(0.5, 1.02,
                                f"sPED$_{{2020}}$: {sped_0_ref:.0f}"
                                r" kWh/(m$^2$ yr)",
                                transform=ax.transAxes,
                                ha="center", va="bottom",
                                fontsize=9, color="#555555", **_fp)

                # Y-axis scenario labels on every column
                ax.set_yticks(y_pos)
                ax.set_yticklabels(
                    [short_scen[s] for s in scen_order],
                    fontsize=10, **_fp)

                # X-axis ticks on both rows
                ax.xaxis.set_major_locator(MaxNLocator(nbins=3,
                                                        integer=True))
                ax.tick_params(axis="x", labelsize=8.5)

        # X-axis label (above legend)
        fig.text(0.52, 0.065,
                 r"Specific primary energy demand [kWh/(m$^2$ yr)]",
                 ha="center", fontsize=11, **_fp)

        # Row labels
        for row_i, pef_type in enumerate(PEF_TYPES):
            pef_label = "Constant PEF" if pef_type == "constant" \
                else "Decreasing PEF"
            axes[row_i, 0].annotate(
                pef_label, xy=(0, 0.5),
                xytext=(-0.42, 0.5),
                xycoords="axes fraction",
                textcoords="axes fraction",
                fontsize=11, rotation=90, va="center", ha="center",
                **_fb)

        # Legend
        legend_handles = [
            Patch(facecolor=start_end_color, edgecolor="none",
                  label=f"sPED {yr_target}"),
        ]
        for drv in reversed(driver_order):
            if drv in used_drivers:
                legend_handles.append(
                    Patch(facecolor=driver_colors[drv],
                          edgecolor="none",
                          label=drv.replace("\n", " ")))
        # Baseline line entry (matches dashed style in figure)
        from matplotlib.lines import Line2D
        legend_handles.append(
            Line2D([0], [0], color="#444444", linewidth=1.8,
                   linestyle="--", label="sPED 2020"))
        # Hatched entry: use actual driver color so it matches the figure
        legend_handles.append(
            Patch(facecolor=driver_colors["New\nconstruction"],
                  edgecolor="#222222",
                  hatch="//////", linewidth=1.5,
                  label="Increasing sPED"))

        _fp_legend = {"family": "Lato", "weight": 300, "size": 10.5}
        fig.legend(handles=legend_handles, loc="lower center",
                   ncol=len(legend_handles),
                   bbox_to_anchor=(0.52, 0.005), fontsize=10.5,
                   frameon=True, edgecolor="#cccccc",
                   fancybox=True, prop=_fp_legend)
        fig.tight_layout(rect=[0.04, 0.08, 1, 0.94])
        fig.subplots_adjust(hspace=0.28, wspace=0.22)
        save_fig(fig, f"fig_waterfall_h_{yr_target}",
                 directory=WATERFALL_DIR)

    # Restore default font
    matplotlib.rcParams.update({
        "font.family": "sans-serif", "font.weight": "normal",
    })


def fig10_waterfall_by_scenario(df_all, df_existing):
    """Horizontal bar waterfall grouped by scenario.

    Layout: 2x2 grid (one panel per scenario).
    Each panel has 7 countries on the y-axis, 2 bars per country
    (constant PEF = solid, decreasing PEF = subtle hatched).
    Reducing drivers stack rightward; worsening drivers are isolated
    after a gap and stack rightward with dark border and "+" labels.
    No sPED 2020 baseline line (bars visually end at the same point).
    """
    print("Generating Fig 10: Waterfall by scenario...")

    import matplotlib
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    from matplotlib.ticker import MaxNLocator

    # --- Font ---
    _fp = {"family": "Lato", "weight": 300}
    _fb = {"family": "Lato", "weight": 600}
    matplotlib.rcParams.update({"font.family": "Lato", "font.weight": 300})

    # --- Colorblind-friendly palette (same as fig9) ---
    driver_colors = {
        "New\nconstruction": "#009E73",   # bluish green (Okabe-Ito)
        "FED\nsavings": "#56B4E9",        # sky blue (Okabe-Ito)
        "Ambient &\nsolar": "#E69F00",    # orange (Okabe-Ito)
        "PEF\neffect": "#CC79A7",         # reddish purple (Okabe-Ito)
    }
    start_end_color = "#2C3E50"

    driver_order = ["PEF\neffect", "Ambient &\nsolar",
                    "FED\nsavings", "New\nconstruction"]

    scen_order = ["Regulatory+", "Regulatory", "Moderate", "Economics+"]
    worsen_gap = 4  # kWh gap before worsening segments
    # Bar heights: equal for both PEF types
    bar_h_const = 0.36
    bar_h_decr = 0.36

    for yr_target in [2030, 2035, 2050]:
        fig, axes = plt.subplots(2, 2, figsize=(18, 10))
        # Precompute all decompositions
        all_decomp = {}
        for country in COUNTRIES:
            for pef_type in PEF_TYPES:
                for scenario in scen_order:
                    sped_0, bars, sped_t = _waterfall_decompose(
                        df_all, df_existing, country, scenario,
                        pef_type, 2020, yr_target)
                    all_decomp[(country, pef_type, scenario)] = (
                        sped_0, bars, sped_t)

        used_drivers = set()
        has_worsening = False

        # Bar positioning: thick const + thin decr per country
        # Larger gaps make room for + bars drawn above each row without
        # overlap between C/D pairs or adjacent countries.
        group_gap = 0.55
        pair_gap = 0.32

        y_positions = {}
        y_country_centers = []
        bar_heights = {}
        y = 0
        for ci, country in enumerate(COUNTRIES):
            y_positions[(ci, 0)] = y
            bar_heights[(ci, 0)] = bar_h_const
            y_positions[(ci, 1)] = y + bar_h_const + pair_gap
            bar_heights[(ci, 1)] = bar_h_decr
            y_country_centers.append(
                y + (bar_h_const + pair_gap + bar_h_decr) / 2)
            y += bar_h_const + pair_gap + bar_h_decr + group_gap

        import matplotlib.transforms as mtransforms
        panel_pos = [(0, 0), (0, 1), (1, 0), (1, 1)]

        # Compute GLOBAL x-range shared across all 4 panels
        g_x_min = 999
        g_x_max = 0
        for scenario in scen_order:
            for country in COUNTRIES:
                for pef_type in PEF_TYPES:
                    s0, bb, st = all_decomp[(country, pef_type, scenario)]
                    if bb and not np.isnan(s0):
                        g_x_min = min(g_x_min, st)
                        ext = st + sum(abs(v) for _, v in bb)
                        g_x_max = max(g_x_max, s0, ext)
        x_lo = max(0, g_x_min - 15)
        x_hi = g_x_max * 1.05

        for si, scenario in enumerate(scen_order):
            r, c = panel_pos[si]
            ax = axes[r, c]

            for ci, country in enumerate(COUNTRIES):
                for pi, pef_type in enumerate(PEF_TYPES):
                    yp = y_positions[(ci, pi)]
                    bh = bar_heights[(ci, pi)]
                    sped_0, bars, sped_t = all_decomp[
                        (country, pef_type, scenario)]
                    if not bars or np.isnan(sped_0):
                        continue

                    bar_dict = {lbl: val for lbl, val in bars}

                    # Font sizes for segment labels
                    fs_lg = 9
                    fs_sm = 7.5

                    bar_center_y = yp

                    # --- 1. Gray bar from x_lo to sped_t ---
                    ax.barh(yp, sped_t - x_lo, bh, left=x_lo,
                            facecolor="#D4D4D4",
                            edgecolor="white", linewidth=0.5,
                            zorder=2)

                    # --- 2. Stack from sped_0 leftward ---
                    # Absorb small negative values (< 3 kWh) into
                    # FED savings to avoid tiny visual extensions.
                    fed_key = "FED\nsavings"
                    for drv in driver_order:
                        v = bar_dict.get(drv, 0)
                        if drv != fed_key and -3 < v < 0:
                            bar_dict[fed_key] = bar_dict.get(fed_key, 0) + v
                            bar_dict[drv] = 0

                    # Waterfall: worsening drivers push sPED UP from the
                    # 2020 baseline (drawn above main row); reducing drivers
                    # then bring it DOWN from the peak to sped_t (main row).
                    # + bars always go ABOVE the main row for both C and D
                    # so "up means worsening" is a consistent visual rule.
                    # Row spacing (group_gap, pair_gap) guarantees no overlap.
                    bh_worsen = bh * 0.55
                    yp_worsen = yp - bh / 2 - bh_worsen / 2

                    # Sum of worsening values
                    sum_worsen = 0
                    for drv in driver_order:
                        v = bar_dict.get(drv, 0)
                        if v < -0.3:
                            sum_worsen += abs(v)
                    peak = sped_0 + sum_worsen  # top of the waterfall

                    # First pass: worsening bars (negative values),
                    # drawn above main row, extending right from sped_0
                    run_worsen = sped_0
                    for drv in driver_order:
                        val = bar_dict.get(drv, 0)
                        if val > -0.3:
                            continue
                        used_drivers.add(drv)
                        clr = driver_colors[drv]
                        w = abs(val)
                        ax.barh(yp_worsen, w, bh_worsen, left=run_worsen,
                                color=clr, edgecolor="white",
                                linewidth=0.5, zorder=4)
                        mid_x = run_worsen + w / 2
                        _fs = 9 if w >= 6 else 7
                        ax.text(mid_x, yp_worsen, "+",
                                ha="center", va="center",
                                fontsize=_fs, color="white",
                                zorder=5, clip_on=True, **_fb)
                        run_worsen = run_worsen + w

                    # Connector: thin line from the end of the worsen
                    # stack down to the top of the main reducing row,
                    # showing the "step down" of a waterfall.
                    if sum_worsen > 0.3:
                        y_connector_top = yp_worsen + bh_worsen / 2
                        y_connector_bot = yp - bh / 2
                        ax.plot([peak, peak],
                                [y_connector_top, y_connector_bot],
                                color="#555555", linewidth=0.8,
                                linestyle="-", zorder=4)

                    # Second pass: reducing bars (positive values),
                    # chained from the peak (end of worsening stack) on
                    # the main row, going left down to sped_t
                    run = peak
                    for drv in driver_order:
                        val = bar_dict.get(drv, 0)
                        if val < 0.3:
                            continue
                        used_drivers.add(drv)
                        clr = driver_colors[drv]
                        left = run - val
                        ax.barh(yp, val, bh, left=left,
                                color=clr, edgecolor="white",
                                linewidth=0.5, zorder=3)
                        mid_x = left + val / 2
                        if val >= 6:
                            ax.text(mid_x, bar_center_y, "\u2212",
                                    ha="center", va="center",
                                    fontsize=11, color="white",
                                    zorder=5, clip_on=True, **_fb)
                        run = left

                    # Store sped_0 for combined baseline line
                    if pi == 0:
                        _sped_0_for_baseline = sped_0

                # Solid vertical baseline line spanning both C and D bars
                yp_c = y_positions[(ci, 0)]
                yp_d = y_positions[(ci, 1)]
                bh_c = bar_heights[(ci, 0)]
                bh_d = bar_heights[(ci, 1)]
                y_top = yp_c - bh_c / 2 - 0.06
                y_bot_line = yp_d + bh_d / 2 + 0.06
                ax.plot([_sped_0_for_baseline, _sped_0_for_baseline],
                        [y_top, y_bot_line],
                        color="black", linewidth=2.5,
                        linestyle="-", zorder=6)

                # EPBD Article 9(2) target lines per country
                if yr_target == 2030:
                    # 16% reduction target
                    target_x = _sped_0_for_baseline * (1 - 0.16)
                    ax.plot([target_x, target_x],
                            [y_top, y_bot_line],
                            color="#d62728", linewidth=1.5,
                            linestyle="--", zorder=5, alpha=0.85)
                elif yr_target == 2035:
                    # 20% to 22% reduction target range
                    target_x_low = _sped_0_for_baseline * (1 - 0.20)
                    target_x_high = _sped_0_for_baseline * (1 - 0.22)
                    ax.plot([target_x_low, target_x_low],
                            [y_top, y_bot_line],
                            color="#d62728", linewidth=1.5,
                            linestyle="--", zorder=5, alpha=0.85)
                    ax.plot([target_x_high, target_x_high],
                            [y_top, y_bot_line],
                            color="#d62728", linewidth=1.5,
                            linestyle="--", zorder=5, alpha=0.85)

            # sPED labels removed — legend + caption explain the reading direction

            ax.set_xlim(x_lo, x_hi)
            # Tight bottom: just below last bar (Sweden D)
            y_bot = y_positions[(len(COUNTRIES) - 1, 1)] + bar_h_decr / 2 + 0.15
            ax.set_ylim(y_bot, -0.15)

            # Major + minor gridlines for easier value reading
            from matplotlib.ticker import AutoMinorLocator
            ax.xaxis.set_major_locator(MaxNLocator(nbins=6, integer=True))
            ax.xaxis.set_minor_locator(AutoMinorLocator(2))
            ax.grid(True, axis="x", which="major", alpha=0.20, linewidth=0.5)
            ax.grid(True, axis="x", which="minor", alpha=0.10, linewidth=0.3,
                    linestyle=":")
            ax.grid(True, axis="y", alpha=0.18, linewidth=0.3)

            # Spines: show top for secondary axis, hide right
            ax.spines["top"].set_visible(True)
            ax.spines["top"].set_linewidth(0.5)
            ax.spines["top"].set_color("#999999")
            ax.spines["right"].set_visible(False)

            # Secondary x-axis at top (mirror of bottom)
            ax.tick_params(axis="x", which="both", top=True,
                           labeltop=True, labelsize=8.5)
            ax.tick_params(axis="x", which="major", top=True,
                           length=4, width=0.5, color="#999999")
            ax.tick_params(axis="x", which="minor", top=True,
                           length=2, width=0.4, color="#999999")

            # Panel title
            ax.set_title(scenario, fontsize=15, pad=28, **_fb)

            # Y-axis: C/D labels next to each bar
            cd_ticks = []
            cd_labels = []
            for ci in range(len(COUNTRIES)):
                cd_ticks.append(y_positions[(ci, 0)])
                cd_labels.append("C")
                cd_ticks.append(y_positions[(ci, 1)])
                cd_labels.append("D")
            ax.set_yticks(cd_ticks)
            ax.set_yticklabels(cd_labels, fontsize=9,
                               color="#333333", **_fb)
            ax.tick_params(axis="y", length=0, pad=3)
            # Country names centered between C/D pair
            import matplotlib.transforms as mtransforms
            trans = mtransforms.blended_transform_factory(
                ax.transAxes, ax.transData)
            for ci, country in enumerate(COUNTRIES):
                ax.text(-0.08, y_country_centers[ci], country,
                        ha="right", va="center", fontsize=11,
                        transform=trans, clip_on=False, **_fb)

            # X-axis label (bottom only)
            ax.tick_params(axis="x", labelsize=9.5)
            ax.set_xlabel(
                r"Specific primary energy demand [kWh/(m$^2$ yr)]",
                fontsize=11, **_fp)

        # Legend
        if yr_target == 2030:
            _target_label = "EPBD 2030 target (16%)"
        elif yr_target == 2035:
            _target_label = "EPBD 2035 target (20% to 22%)"
        else:
            _target_label = None
        legend_handles = [
            Patch(facecolor="#D4D4D4", edgecolor="white",
                  linewidth=0.5, label=f"sPED ({yr_target})"),
            Line2D([], [], color="black", linewidth=2.5,
                   linestyle="-", label="sPED 2020 baseline"),
        ]
        if _target_label is not None:
            legend_handles.append(
                Line2D([], [], color="#d62728", linewidth=1.5,
                       linestyle="--", label=_target_label))
        legend_label_map = {
            "New\nconstruction": "New buildings effect",
        }
        for drv in reversed(driver_order):
            if drv in used_drivers:
                lbl = legend_label_map.get(drv, drv.replace("\n", " "))
                legend_handles.append(
                    Patch(facecolor=driver_colors[drv],
                          edgecolor="none",
                          label=lbl))
        # PEF label note
        legend_handles.append(
            Line2D([], [], color="none", marker="none",
                   label="C = Constant PEF;  D = Decreasing PEF"))


        _fp_legend = {"family": "Lato", "weight": 300, "size": 11}
        fig.legend(handles=legend_handles, loc="lower center",
                   ncol=4,
                   bbox_to_anchor=(0.52, -0.005), fontsize=11,
                   frameon=True, edgecolor="#cccccc",
                   fancybox=True, prop=_fp_legend)
        fig.tight_layout(rect=[0.07, 0.08, 1, 0.95])
        fig.subplots_adjust(hspace=0.45, wspace=0.22)
        save_fig(fig, f"fig_waterfall_scen_{yr_target}")

    # Restore default font
    matplotlib.rcParams.update({
        "font.family": "sans-serif", "font.weight": "normal",
    })


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    # Generates the figures used in the paper:
    #   fig_total_fed_carrier        (residential FED by energy carrier)
    #   fig_specific_ped_residential (sPED reduction trajectories)
    #   fig_waterfall_scen_2030/2035 (driver decomposition by scenario)
    setup_style()

    print("Loading data...")
    df_output1 = load_output1()
    df_target2 = load_target2()
    df_target2_ex = load_target2_existing()
    print(f"  output_1:            {len(df_output1)} rows")
    print(f"  target indicators:   {len(df_target2)} rows")
    print(f"  existing-stock data: {len(df_target2_ex)} rows")

    fig2b_total_fed_carrier(df_output1)
    fig3_specific_ped(df_target2)
    fig10_waterfall_by_scenario(df_target2, df_target2_ex)

    print("\nPaper figures generated.")
