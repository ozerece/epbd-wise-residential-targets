# Data

All data were produced within the EPBD.wise project using the Invert/Opt
building stock model and supporting databases (Eurostat energy balances,
Tabula/Episcope building typologies, national statistics). The model was
calibrated to the 2020 base year. Files are licensed CC BY 4.0 (see
`../LICENSE-data.md`).

Countries analysed: Finland (FIN), France (FRA), Germany (DEU), Ireland (IRL),
Poland (XOL/POL), Romania (XOU/ROU), Sweden (SWE).

Policy scenarios: `Regulatory+`, `Regulatory`, `Moderate`, `Economics`
(`Economics+` in the raw files), each run under a constant and a decreasing
primary energy factor (PEF) assumption.

## Files

| File | Description | Used for |
|------|-------------|----------|
| `output_1_all.xlsx` | Model output for the **full** building stock (existing + new): final energy demand (FED), primary energy demand (PED), area-specific PED (sPED), heated gross floor area, by country, scenario, PEF case, year, energy carrier and end use. | Main figures (FED carrier mix, sPED trajectories, decomposition) |
| `output_1_existing.xlsx` | As above, for the **existing** stock only. Used together with `output_1_all.xlsx` to isolate the new-buildings effect in the driver decomposition. | Driver decomposition (waterfall) |
| `target_indicators_2_all.xlsx` | Earlier full-stock indicator file. Used as a fallback for any country/scenario missing from `output_1_all.xlsx`. | Fallback loader |
| `target_indicators_2_existing.xlsx` | Earlier existing-stock indicator file; fallback for `output_1_existing.xlsx`. | Fallback loader |
| `dist_curve.xlsx` | Cumulative distribution of specific primary energy demand across the residential stock at the 2020 baseline, by country, building category (single-family / multi-family), and service-factor treatment. | Minimum energy performance standard (MEPS) thresholds table |
| `PEFs_input_EPBDwise_EU27_2025-12-09.csv` | Country-specific primary energy factors for electricity and district heating used as model inputs. | PEF values table |
| `WPB_data_merged.csv` | Worst-performing-buildings (WPB) data: building segments ranked by specific final energy demand, used for the Article 9(2) distributional requirement (55% of savings from the worst-performing 43% of floor area). | Section on the distributional requirement |

## Key columns (model output files)

- `nuts0_id` — country code
- `scenario_id` — policy scenario
- `PEF` — `constant` or `decreasing`
- `year` — model year (2020, 2030, 2035, 2050)
- `data_type_id` — `FED`, `PED_incl_sf`, `area-specific PED_incl_sf`,
  `Heated gross floor area`, `UED`, etc.
- `sector_id` — `Residential` / `Tertiary`
- `end_use_id` — `Space heating`, `Water heating`, `Cooling`
- `energy_carrier_id` — coal, oil, gas, biomass, electricity, district heating,
  ambient heat, solar thermal, PV space heating & DHW (and `... from RES`
  variants, merged into their parent carrier in the analysis)
- `value` — quantity in the units implied by `data_type_id`

## Notes

- The compliance metric (sPED) is computed from space heating and domestic hot
  water only; cooling is reported separately as useful energy demand and does
  not enter the sPED accounting.
- The MEPS thresholds reported in the paper use the **service-factor-adjusted**,
  building-type-specific values from `dist_curve.xlsx`.
