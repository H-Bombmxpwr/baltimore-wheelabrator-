"""
Wheelabrator Baltimore / BRESCO emissions data.

The facility is NOT in the EPA TRI database (municipal waste combustors are often exempt).
Data is compiled from:
- EPA National Emissions Inventory (NEI) 2014, 2017
- Clean Air Baltimore (cleanairbmore.org)
- MDE permit records
- EPA GHG Reporting Program (facility ID 1004094)

Source: https://cleanairbmore.org/incineration/wheelabrator/
"""

import os
import pandas as pd
from src.config import DATA_DIR

# EPA NEI data for Wheelabrator Baltimore (lbs/year)
EMISSIONS_DATA = {
    2014: {
        "NOx": 2_151_526,
        "SO2": 621_703,
        "HCl": 147_404,
        "CO": 131_905,
        "PM": 49_801,
        "PM2.5": 46_174,
        "Formaldehyde": 3_966,
        "VOC": 6_600,
        "HF": 482,
        "Lead": 294,
        "Mercury": 53,
        "Nickel": 17,
        "Chromium_VI": 4,
    },
    2017: {
        "NOx": 2_202_482,
        "SO2": 616_154,
        "HCl": 156_805,
        "CO": 149_817,
        "PM": 57_999,
        "PM2.5": 54_521,
        "Formaldehyde": 4_022,
        "VOC": 5_398,
        "HF": 1_019,
        "Lead": 247,
        "Mercury": 29,
        "Nickel": 92,
        "Chromium_VI": 2,
    },
}

# GHG emissions (metric tons CO2e/year)
GHG_DATA = {
    2017: 762_683,
}

# Context: Baltimore's single largest stationary source of air pollution
# SO2 from Wheelabrator ≈ half of all SO2 emissions in Baltimore City
# Produces more mercury, lead, and GHGs per hour than each of MD's four largest coal plants


def get_emissions_df():
    """Return emissions data as a tidy DataFrame."""
    rows = []
    for year, pollutants in EMISSIONS_DATA.items():
        for pollutant, lbs in pollutants.items():
            rows.append({
                "year": year,
                "pollutant": pollutant,
                "lbs_per_year": lbs,
                "tons_per_year": round(lbs / 2000, 1),
                "kg_per_year": round(lbs * 0.453592, 1),
            })
    return pd.DataFrame(rows)


def get_ghg_df():
    """Return GHG data."""
    rows = [{"year": y, "co2e_metric_tons": v} for y, v in GHG_DATA.items()]
    return pd.DataFrame(rows)


def save_emissions():
    os.makedirs(DATA_DIR, exist_ok=True)

    df = get_emissions_df()
    path = os.path.join(DATA_DIR, "wheelabrator_emissions.csv")
    df.to_csv(path, index=False)
    print(f"Saved emissions data to {path}")

    ghg = get_ghg_df()
    path2 = os.path.join(DATA_DIR, "wheelabrator_ghg.csv")
    ghg.to_csv(path2, index=False)
    print(f"Saved GHG data to {path2}")

    return df, ghg


def print_summary():
    df = get_emissions_df()
    print("=== Wheelabrator Baltimore Emissions Summary ===\n")
    for year in sorted(df["year"].unique()):
        print(f"--- {year} ---")
        subset = df[df["year"] == year].sort_values("tons_per_year", ascending=False)
        for _, row in subset.iterrows():
            print(f"  {row['pollutant']:20s} {row['tons_per_year']:>10.1f} tons/yr  ({row['lbs_per_year']:>12,} lbs)")
        print()


if __name__ == "__main__":
    print_summary()
    save_emissions()
