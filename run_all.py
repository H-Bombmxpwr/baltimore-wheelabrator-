"""
Main runner: fetch all data and generate all visualizations.

Usage:
    python run_all.py              # Full pipeline (needs AQS API key in .env)
    python run_all.py --wind-only  # Just wind data + wind rose (no API key needed)
    python run_all.py --no-aqs     # Skip AQS (emissions + wind only, no API key needed)
"""

import sys
import os

# Run from project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from src.fetch_wind import fetch_wind_data, save_wind_data, load_wind_data
from src.fetch_emissions import get_emissions_df, save_emissions, print_summary
from src.visualize import (
    plot_wind_rose, plot_seasonal_wind_roses, create_map,
    plot_facility_emissions,
)


def run_wind(use_cached=True):
    cache_path = "data/wind_bwi.csv"
    if use_cached and os.path.exists(cache_path):
        print("Loading cached wind data...")
        return load_wind_data()
    else:
        print("Fetching wind data from Iowa Mesonet (this takes a minute)...")
        df = fetch_wind_data()
        save_wind_data(df)
        return df


def run_emissions():
    print("\n=== Facility Emissions Data ===")
    print_summary()
    emissions_df, ghg_df = save_emissions()
    return emissions_df


def run_aqs():
    from src.fetch_aqs import discover_monitors, fetch_all_pollutants, save_aqs_data
    from src.config import AQS_COUNTY_CITY, AQS_COUNTY_CO

    print("\n=== AQS Data ===")
    print("Discovering monitors...")
    monitors = discover_monitors(AQS_COUNTY_CITY)
    monitors_co = discover_monitors(AQS_COUNTY_CO)
    import pandas as pd
    monitors = pd.concat([monitors, monitors_co], ignore_index=True)

    print("Fetching pollutant data (this may take several minutes)...")
    city_data = fetch_all_pollutants(AQS_COUNTY_CITY)
    county_data = fetch_all_pollutants(AQS_COUNTY_CO)

    merged = {}
    all_keys = set(list(city_data.keys()) + list(county_data.keys()))
    for key in all_keys:
        frames = [city_data.get(key), county_data.get(key)]
        frames = [f for f in frames if f is not None]
        if frames:
            merged[key] = pd.concat(frames, ignore_index=True)

    save_aqs_data(monitors, merged)
    return monitors, merged


def run_analysis_and_viz(wind_df, emissions_df=None, monitors_df=None, aqs_data=None):
    from src.analyze import classify_wind_for_monitor, classify_wind_for_i95, merge_aqi_wind, directional_analysis, seasonal_directional_analysis
    from src.visualize import plot_pollution_rose, plot_directional_comparison, plot_seasonal_comparison, plot_time_series

    print("\n=== Visualizations ===")

    # Always generate wind roses
    print("Generating wind roses...")
    plot_wind_rose(wind_df)
    plot_seasonal_wind_roses(wind_df)

    # Always generate the map
    print("Generating interactive map...")
    create_map(monitors_df)

    # Facility emissions chart
    if emissions_df is not None and not emissions_df.empty:
        print("Generating facility emissions chart...")
        plot_facility_emissions(emissions_df)

    # If we have AQS data, do the directional analysis
    if aqs_data and "PM2.5" in aqs_data:
        print("\nRunning directional analysis for PM2.5...")
        pm25 = aqs_data["PM2.5"]

        # Get unique monitor locations
        if "latitude" in pm25.columns and "longitude" in pm25.columns:
            sites = pm25.groupby(["latitude", "longitude"]).size().reset_index()

            for _, site in sites.iterrows():
                lat, lon = site["latitude"], site["longitude"]
                site_data = pm25[(pm25["latitude"] == lat) & (pm25["longitude"] == lon)]

                print(f"\n  Monitor at ({lat:.3f}, {lon:.3f}): {len(site_data)} days")

                # Classify wind for this monitor
                classified = classify_wind_for_monitor(wind_df, lat, lon)
                classified = classify_wind_for_i95(classified, lat, lon)

                # Merge
                merged = merge_aqi_wind(site_data, classified)
                if len(merged) < 30:
                    print("    Too few merged records, skipping")
                    continue

                # Directional analysis
                results = directional_analysis(merged)
                for key, stats in results.items():
                    if stats["mean"] is not None:
                        print(f"    {stats['label']}: mean={stats['mean']}, n={stats['n_days']}")

                # Plots for this monitor
                site_label = f"{lat:.2f}_{lon:.2f}"
                plot_pollution_rose(merged, pollutant="PM2.5",
                                    filename=f"pollution_rose_{site_label}.html")
                plot_directional_comparison(results, pollutant="PM2.5",
                                            filename=f"directional_{site_label}.html")
                plot_time_series(merged, pollutant="PM2.5",
                                 filename=f"timeseries_{site_label}.html")

                seasonal = seasonal_directional_analysis(merged)
                plot_seasonal_comparison(seasonal, pollutant="PM2.5",
                                         filename=f"seasonal_{site_label}.html")

    print("\n=== Done! ===")
    print(f"Output files are in the '{os.path.abspath('output')}' directory.")
    print("Open the .html files in your browser to explore.")


def main():
    args = sys.argv[1:]
    wind_only = "--wind-only" in args
    no_aqs = "--no-aqs" in args

    print("=" * 60)
    print("Baltimore Air Quality Analysis")
    print("Wheelabrator/WIN Waste vs I-95 Corridor")
    print("=" * 60)

    # Step 1: Wind data (always)
    print("\n=== Wind Data ===")
    wind_df = run_wind()
    print(f"Wind data: {len(wind_df)} records, {wind_df['timestamp'].min()} to {wind_df['timestamp'].max()}")

    if wind_only:
        run_analysis_and_viz(wind_df)
        return

    # Step 2: Facility emissions (compiled data, no API needed)
    emissions_df = run_emissions()

    # Step 3: AQS data (optional, needs API key)
    monitors_df = None
    aqs_data = None
    if not no_aqs:
        try:
            monitors_df, aqs_data = run_aqs()
        except RuntimeError as e:
            print(f"\nSkipping AQS: {e}")
            print("Run with --no-aqs to skip, or set up your .env file")
    else:
        print("\nSkipping AQS data (--no-aqs)")

    # Step 4: Analysis and visualization
    run_analysis_and_viz(wind_df, emissions_df, monitors_df, aqs_data)


if __name__ == "__main__":
    main()
