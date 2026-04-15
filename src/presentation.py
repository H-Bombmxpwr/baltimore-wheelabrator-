"""
Presentation helpers for the Baltimore air quality project.
"""

from functools import lru_cache
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analyze import (
    angle_diff,
    bearing_from,
    classify_wind_for_i95,
    classify_wind_for_monitor,
    merge_aqi_wind,
    nearest_point_on_polyline,
)
from src.config import DATA_DIR, I95_WAYPOINTS, NEIGHBORHOODS, WHEELABRATOR
from src.fetch_emissions import EMISSIONS_DATA, get_emissions_df, get_ghg_df
from src.fetch_wind import load_wind_data


CACHE_DIR = "presentation_assets"
CATEGORY_ORDER = ["Wheelabrator only", "I-95 only", "Both", "Neither"]
CATEGORY_COLORS = {
    "Wheelabrator only": "#bf3f34",
    "I-95 only": "#d88c2d",
    "Both": "#7a5c99",
    "Neither": "#7d8794",
}
GROUP_COLORS = {
    "Near both": "#bf3f34",
    "I-95 only": "#d88c2d",
    "Control": "#7d8794",
}
PRESENTATION_IMAGES = {
    "study_area": "presentation_study_area.png",
    "wheelabrator_photo": "wheelabrator.jpg",
    "aqs_photo": "aqs_monitor.jpg",
    "bwi_photo": "bwi.jpg",
    "workflow": "presentation_method_flow.png",
    "emissions": "presentation_emissions_summary.png",
    "pm25_summary": "presentation_pm25_summary.png",
    "monitor_delta": "presentation_monitor_deltas.png",
    "seasonal_summary": "presentation_seasonal_summary.png",
    "confounders": "presentation_confounders.png",
}

REGIONAL_TRANSPORT_QUADRANT = (180, 270)


def _ensure_output():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _format_pct(value):
    if value is None or pd.isna(value):
        return "n/a"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def _count_or_zero(value):
    return int(value) if pd.notna(value) else 0


def _haversine_km(lat1, lon1, lat2, lon2):
    radius_km = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return radius_km * 2 * math.asin(math.sqrt(a))


def _nearest_neighborhood(lat, lon):
    best_name = None
    best_distance = float("inf")
    for name, info in NEIGHBORHOODS.items():
        distance = _haversine_km(lat, lon, info["lat"], info["lon"])
        if distance < best_distance:
            best_name = name
            best_distance = distance
    return best_name, best_distance


def _season_name(month):
    return {
        12: "Winter", 1: "Winter", 2: "Winter",
        3: "Spring", 4: "Spring", 5: "Spring",
        6: "Summer", 7: "Summer", 8: "Summer",
        9: "Fall", 10: "Fall", 11: "Fall",
    }[month]


def _load_pm25_daily():
    path = os.path.join(DATA_DIR, "aqs_pm25.csv")
    if not os.path.exists(path):
        return pd.DataFrame()

    df = pd.read_csv(path, parse_dates=["date_local"])
    if df.empty:
        return df

    return df.groupby(["latitude", "longitude", "date_local"], as_index=False).agg(
        arithmetic_mean=("arithmetic_mean", "mean"),
        aqi=("aqi", "mean"),
        local_site_name=("local_site_name", "first"),
        site_number=("site_number", "first"),
        county=("county", "first"),
        city=("city", "first"),
    )


def _categorize_downwind(df):
    categorized = df.copy()
    categorized["category"] = "Neither"
    categorized.loc[
        (categorized["pct_downwind_wheelabrator"] > 0.5)
        & (categorized["pct_downwind_i95"] <= 0.5),
        "category",
    ] = "Wheelabrator only"
    categorized.loc[
        (categorized["pct_downwind_wheelabrator"] <= 0.5)
        & (categorized["pct_downwind_i95"] > 0.5),
        "category",
    ] = "I-95 only"
    categorized.loc[
        (categorized["pct_downwind_wheelabrator"] > 0.5)
        & (categorized["pct_downwind_i95"] > 0.5),
        "category",
    ] = "Both"
    return categorized


def _monitor_note(row):
    pct = row["wb_vs_i95_pct"]
    if pct is None or pd.isna(pct):
        return "Not enough clean Wheelabrator-vs-I-95 days to compare this monitor."
    if pct >= 40:
        return "Strongest Wheelabrator signal in the dataset."
    if pct >= 15:
        return "Wheelabrator-only days are meaningfully above I-95-only days."
    if pct >= 0:
        return "Wheelabrator-only days are slightly above I-95-only days."
    return "I-95-only days are higher here, which suggests stronger eastern corridor influences."


@lru_cache(maxsize=1)
def get_presentation_context():
    emissions_df = get_emissions_df()
    ghg_df = get_ghg_df()
    wind_df = load_wind_data()
    pm25_daily = _load_pm25_daily()

    total_2014 = sum(EMISSIONS_DATA[2014].values())
    total_2017 = sum(EMISSIONS_DATA[2017].values())
    total_pct = round((total_2017 - total_2014) / total_2014 * 100, 1)

    sectors = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    sector_ids = (((wind_df["wind_dir"] + 22.5) % 360) // 45).astype(int)
    sector_share = (
        sector_ids.map(dict(enumerate(sectors)))
        .value_counts(normalize=True)
        .reindex(sectors)
        .fillna(0)
        .mul(100)
        .round(1)
    )
    top_wind = sector_share.sort_values(ascending=False).head(3)

    monitor_summary = []
    confound_rows = []
    merged_frames = []
    if not pm25_daily.empty:
        for (lat, lon), site_df in pm25_daily.groupby(["latitude", "longitude"]):
            wind_for_site = classify_wind_for_monitor(wind_df, lat, lon)
            wind_for_site = classify_wind_for_i95(wind_for_site, lat, lon)
            merged = merge_aqi_wind(site_df, wind_for_site)
            if len(merged) < 30:
                continue

            merged = _categorize_downwind(merged)

            bearing_wb = bearing_from(lat, lon, WHEELABRATOR["lat"], WHEELABRATOR["lon"])
            i95_point = nearest_point_on_polyline(lat, lon, I95_WAYPOINTS)
            bearing_i95 = bearing_from(lat, lon, i95_point[0], i95_point[1])
            angular_offset = round(angle_diff(bearing_wb, bearing_i95), 1)

            wb_only = merged[merged["category"] == "Wheelabrator only"]
            if len(wb_only):
                lo, hi = REGIONAL_TRANSPORT_QUADRANT
                sw_mask = (wb_only["mean_wind_dir"] >= lo) & (wb_only["mean_wind_dir"] < hi)
                regional_share = round(float(sw_mask.mean()) * 100, 1)
                regional_n = int(sw_mask.sum())
            else:
                regional_share = None
                regional_n = 0
            site_name = site_df["local_site_name"].iloc[0]
            nearest_name, nearest_distance = _nearest_neighborhood(lat, lon)
            category_stats = (
                merged.groupby("category")["arithmetic_mean"]
                .agg(mean="mean", median="median", count="size")
                .reindex(CATEGORY_ORDER)
            )
            wb_mean = category_stats.loc["Wheelabrator only", "mean"]
            i95_mean = category_stats.loc["I-95 only", "mean"]
            both_mean = category_stats.loc["Both", "mean"]
            neither_mean = category_stats.loc["Neither", "mean"]
            wb_vs_i95 = (
                round((wb_mean - i95_mean) / i95_mean * 100, 1)
                if pd.notna(wb_mean) and pd.notna(i95_mean) and i95_mean
                else None
            )
            both_vs_neither = (
                round((both_mean - neither_mean) / neither_mean * 100, 1)
                if pd.notna(both_mean) and pd.notna(neither_mean) and neither_mean
                else None
            )

            monitor_row = {
                "site_name": site_name,
                "site_label": f"{site_name} ({lat:.2f}, {lon:.2f})",
                "chart_label": f"{lat:.2f}_{lon:.2f}",
                "lat": float(lat),
                "lon": float(lon),
                "nearest_neighborhood": nearest_name,
                "nearest_distance_km": round(nearest_distance, 1),
                "distance_from_wheelabrator_km": round(
                    _haversine_km(lat, lon, WHEELABRATOR["lat"], WHEELABRATOR["lon"]), 1
                ),
                "n_days": int(len(merged)),
                "wb_mean": round(wb_mean, 2) if pd.notna(wb_mean) else None,
                "i95_mean": round(i95_mean, 2) if pd.notna(i95_mean) else None,
                "both_mean": round(both_mean, 2) if pd.notna(both_mean) else None,
                "neither_mean": round(neither_mean, 2) if pd.notna(neither_mean) else None,
                "wb_n": _count_or_zero(category_stats.loc["Wheelabrator only", "count"]),
                "i95_n": _count_or_zero(category_stats.loc["I-95 only", "count"]),
                "both_n": _count_or_zero(category_stats.loc["Both", "count"]),
                "neither_n": _count_or_zero(category_stats.loc["Neither", "count"]),
                "wb_vs_i95_pct": wb_vs_i95,
                "both_vs_neither_pct": both_vs_neither,
            }
            monitor_row["note"] = _monitor_note(monitor_row)
            monitor_summary.append(monitor_row)

            confound_rows.append(
                {
                    "site_name": site_name,
                    "bearing_to_wheelabrator": round(bearing_wb, 1),
                    "bearing_to_i95": round(bearing_i95, 1),
                    "angular_offset_deg": angular_offset,
                    "regional_share_pct": regional_share,
                    "regional_n": regional_n,
                    "wb_only_n": int(len(wb_only)),
                }
            )

            merged = merged.copy()
            merged["site_name"] = site_name
            merged_frames.append(merged)

    monitor_summary.sort(
        key=lambda row: (
            row["wb_vs_i95_pct"] if row["wb_vs_i95_pct"] is not None else -999,
            -row["distance_from_wheelabrator_km"],
        ),
        reverse=True,
    )

    overall_summary = []
    seasonal_rows = []
    conclusions = []
    if merged_frames:
        all_merged = pd.concat(merged_frames, ignore_index=True)
        all_merged["season"] = all_merged["date_local"].dt.month.map(_season_name)

        overall = (
            all_merged.groupby("category")["arithmetic_mean"]
            .agg(mean="mean", median="median", count="size")
            .reindex(CATEGORY_ORDER)
        )
        for category in CATEGORY_ORDER:
            row = overall.loc[category]
            overall_summary.append(
                {
                    "category": category,
                    "mean": round(row["mean"], 2) if pd.notna(row["mean"]) else None,
                    "median": round(row["median"], 2) if pd.notna(row["median"]) else None,
                    "count": _count_or_zero(row["count"]),
                    "color": CATEGORY_COLORS[category],
                }
            )

        seasonal = (
            all_merged.groupby(["season", "category"])["arithmetic_mean"]
            .agg(mean="mean", count="size")
            .reset_index()
        )
        season_order = ["Winter", "Spring", "Summer", "Fall"]
        for season in season_order:
            season_row = {"season": season}
            subset = seasonal[seasonal["season"] == season].set_index("category")
            for category in CATEGORY_ORDER:
                season_row[category] = (
                    round(subset.loc[category, "mean"], 2)
                    if category in subset.index
                    else None
                )
                season_row[f"{category}_count"] = (
                    int(subset.loc[category, "count"])
                    if category in subset.index
                    else 0
                )
            seasonal_rows.append(season_row)

        wb_overall = next(row for row in overall_summary if row["category"] == "Wheelabrator only")
        i95_overall = next(row for row in overall_summary if row["category"] == "I-95 only")
        both_overall = next(row for row in overall_summary if row["category"] == "Both")
        neither_overall = next(row for row in overall_summary if row["category"] == "Neither")
        wb_delta = round(
            (wb_overall["mean"] - i95_overall["mean"]) / i95_overall["mean"] * 100, 1
        )
        both_delta = round(
            (both_overall["mean"] - neither_overall["mean"]) / neither_overall["mean"] * 100, 1
        )
        monitors_higher = [
            row for row in monitor_summary
            if row["wb_vs_i95_pct"] is not None and row["wb_vs_i95_pct"] > 0
        ]
        strongest_monitor = max(
            monitors_higher,
            key=lambda row: row["wb_vs_i95_pct"],
        ) if monitors_higher else None
        weakest_monitor = min(
            (
                row for row in monitor_summary
                if row["wb_vs_i95_pct"] is not None
            ),
            key=lambda row: row["wb_vs_i95_pct"],
            default=None,
        )

        non_summer_rows = [row for row in seasonal_rows if row["season"] != "Summer"]
        non_summer_note = ""
        if non_summer_rows:
            wb_non_summer = np.mean([row["Wheelabrator only"] for row in non_summer_rows if row["Wheelabrator only"] is not None])
            i95_non_summer = np.mean([row["I-95 only"] for row in non_summer_rows if row["I-95 only"] is not None])
            delta_non_summer = round((wb_non_summer - i95_non_summer) / i95_non_summer * 100, 1)
            non_summer_note = f"I found that in spring, fall, and winter combined, Wheelabrator-only days stayed about {delta_non_summer:.1f}% above I-95-only days."

        lo, hi = REGIONAL_TRANSPORT_QUADRANT
        wb_only_all = all_merged[all_merged["category"] == "Wheelabrator only"]
        if len(wb_only_all):
            regional_mask_all = (wb_only_all["mean_wind_dir"] >= lo) & (wb_only_all["mean_wind_dir"] < hi)
            overall_regional_share = round(float(regional_mask_all.mean()) * 100, 1)
        else:
            overall_regional_share = None

        i95_only_all = all_merged[all_merged["category"] == "I-95 only"]
        if len(i95_only_all):
            i95_regional_mask = (i95_only_all["mean_wind_dir"] >= lo) & (i95_only_all["mean_wind_dir"] < hi)
            i95_regional_share = round(float(i95_regional_mask.mean()) * 100, 1)
        else:
            i95_regional_share = None

        conclusions = [
            f"I found that across all monitor-days in the deduplicated PM2.5 dataset, Wheelabrator-only days averaged {wb_overall['mean']:.2f} ug/m3 versus {i95_overall['mean']:.2f} ug/m3 on I-95-only days, a {wb_delta:.1f}% difference that is directionally consistent with a facility contribution.",
            f"I found that {len(monitors_higher)} of {len(monitor_summary)} PM2.5 monitors showed higher mean PM2.5 on Wheelabrator-only days than on I-95-only days, though the magnitude varied across sites."
            + (
                f" The strongest positive signal appeared at {strongest_monitor['site_name']} ({_format_pct(strongest_monitor['wb_vs_i95_pct'])})."
                if strongest_monitor else ""
            ),
            f"I found that when monitors were downwind of both sources, PM2.5 averaged {both_overall['mean']:.2f} ug/m3, versus {neither_overall['mean']:.2f} ug/m3 on neither days ({both_delta:.1f}% higher).",
            (
                f"I treated {weakest_monitor['site_name']} as a real counter-example rather than a dismissible exception, because I-95-only days were higher there than Wheelabrator-only days ({_format_pct(weakest_monitor['wb_vs_i95_pct'])})."
                if weakest_monitor and weakest_monitor["wb_vs_i95_pct"] is not None and weakest_monitor["wb_vs_i95_pct"] < 0
                else "I did not find a monitor with a stronger I-95-only signal than the Wheelabrator-only signal."
            ),
        ]
        if overall_regional_share is not None:
            conclusions.append(
                f"I could not fully separate the Wheelabrator signal from regional southwesterly transport: {overall_regional_share:.1f}% of Wheelabrator-only monitor-days had mean winds from the 180-270 degree quadrant that also carries Ohio Valley and mid-Atlantic PM2.5 into Baltimore."
            )
        if non_summer_note:
            conclusions.append(non_summer_note)
    else:
        all_merged = pd.DataFrame()
        overall_regional_share = None
        i95_regional_share = None

    positive_monitor_count = len(
        [row for row in monitor_summary if row["wb_vs_i95_pct"] is not None and row["wb_vs_i95_pct"] > 0]
    )

    major_pollutants = []
    for pollutant in ["NOx", "SO2", "HCl", "CO", "PM", "PM2.5", "VOC", "Formaldehyde"]:
        y2014 = emissions_df[(emissions_df["year"] == 2014) & (emissions_df["pollutant"] == pollutant)].iloc[0]
        y2017 = emissions_df[(emissions_df["year"] == 2017) & (emissions_df["pollutant"] == pollutant)].iloc[0]
        pct_change = round((y2017["lbs_per_year"] - y2014["lbs_per_year"]) / y2014["lbs_per_year"] * 100, 1)
        major_pollutants.append(
            {
                "pollutant": pollutant,
                "tons_2014": float(y2014["tons_per_year"]),
                "tons_2017": float(y2017["tons_per_year"]),
                "pct_change": pct_change,
            }
        )

    trace_pollutants = []
    for pollutant in ["HF", "Lead", "Mercury", "Nickel", "Chromium_VI"]:
        y2014 = emissions_df[(emissions_df["year"] == 2014) & (emissions_df["pollutant"] == pollutant)].iloc[0]
        y2017 = emissions_df[(emissions_df["year"] == 2017) & (emissions_df["pollutant"] == pollutant)].iloc[0]
        pct_change = round((y2017["lbs_per_year"] - y2014["lbs_per_year"]) / y2014["lbs_per_year"] * 100, 1)
        trace_pollutants.append(
            {
                "pollutant": pollutant,
                "lbs_2014": int(y2014["lbs_per_year"]),
                "lbs_2017": int(y2017["lbs_per_year"]),
                "pct_change": pct_change,
            }
        )

    context = {
        "facility": WHEELABRATOR,
        "images": PRESENTATION_IMAGES,
        "hero_stats": [
            {"label": "PM2.5 monitors used", "value": str(len(monitor_summary))},
            {"label": "Wind observations", "value": f"{len(wind_df):,}"},
            {"label": "2017 CO2e", "value": f"{int(ghg_df.iloc[0]['co2e_metric_tons']):,} t"},
            {"label": f"{positive_monitor_count} of {len(monitor_summary)} monitors", "value": "WB > I-95"},
        ],
        "outline": [
            "The question and why it matters",
            "The neighborhoods and the data",
            "What Wheelabrator emits, and how the wind moves it",
            "The main PM2.5 finding and what each monitor says",
            "The pressure-test: what else could explain the gap",
            "What I think it means, what I could not answer, what comes next",
        ],
        "study_groups": [
            {"name": "Near both Wheelabrator and I-95", "count": 6, "color": GROUP_COLORS["Near both"]},
            {"name": "I-95 corridor only", "count": 6, "color": GROUP_COLORS["I-95 only"]},
            {"name": "Control neighborhoods", "count": 4, "color": GROUP_COLORS["Control"]},
        ],
        "method_steps": [
            "Pulled Wheelabrator's reported emissions from EPA records.",
            "Pulled six years of hourly wind data from BWI airport.",
            "Pulled daily PM2.5 readings from EPA monitors around Baltimore.",
            "For every monitor-day, tagged the wind as coming from Wheelabrator, I-95, both, or neither.",
            "Compared the PM2.5 numbers across those four buckets, and then looked at seasons and at each monitor on its own.",
        ],
        "emissions_headlines": {
            "nox_tons_2017": 1101.2,
            "so2_tons_2017": 308.1,
            "pm25_tons_2017": 27.3,
            "ghg_2017": int(ghg_df.iloc[0]["co2e_metric_tons"]),
            "total_lbs_2014": total_2014,
            "total_lbs_2017": total_2017,
            "total_pct_change": total_pct,
        },
        "major_pollutants": major_pollutants,
        "trace_pollutants": trace_pollutants,
        "wind_summary": {
            "start": str(wind_df["timestamp"].min().date()),
            "end": str(wind_df["timestamp"].max().date()),
            "records": int(len(wind_df)),
            "mean_speed_ms": round(wind_df["wind_speed_ms"].mean(), 2),
            "top_sectors": [
                {"sector": sector, "share": float(share)}
                for sector, share in top_wind.items()
            ],
            "sector_share": {sector: float(share) for sector, share in sector_share.items()},
        },
        "monitor_summary": monitor_summary,
        "overall_summary": overall_summary,
        "seasonal_summary": seasonal_rows,
        "conclusions": conclusions,
        "confounders": {
            "rows": confound_rows,
            "overall_regional_share": overall_regional_share,
            "i95_regional_share": i95_regional_share,
            "quadrant": REGIONAL_TRANSPORT_QUADRANT,
        },
        "limitations": [
            "I couldn't separate Wheelabrator from regional pollution. The same southwesterly wind that brings the incinerator's plume to most monitors also carries Ohio Valley and mid-Atlantic PM2.5 into Baltimore.",
            "At some monitors, the direction toward Wheelabrator and the direction toward I-95 are basically the same. So the two buckets aren't fully different weather.",
            "I used one weather station at BWI for the whole metro area. Wind can be different a few miles away.",
            "I used daily averages, which smooth out short PM2.5 spikes.",
            "There are no EPA monitors in Westport, Cherry Hill, or Curtis Bay, the neighborhoods right up against the facility.",
            "The facility emissions I compared against are from 2014 and 2017 inventories, while the air quality readings are from 2019-2024.",
        ],
        "recommendations": [
            "Put fence-line monitors in Westport, Cherry Hill, and Curtis Bay, so the neighborhoods closest to the facility are actually being measured.",
            "Subtract a regional pollution background (from an upwind rural monitor, or a transport model) before blaming Wheelabrator for the remainder.",
            "Run this same directional method on sulfur dioxide and nitrogen dioxide. Those pollutants are more unique to local sources than PM2.5, so the fingerprint would be cleaner.",
            "Pair this with a dispersion model or with local wind fields for stronger source attribution.",
            "Refresh the emissions comparison with the most recent reporting data available.",
        ],
        "references": [
            "EPA National Emissions Inventory (2014 and 2017) for facility emissions.",
            "EPA Greenhouse Gas Reporting Program for Wheelabrator CO2e.",
            "EPA Air Quality System daily PM2.5 monitor data for Baltimore City and Baltimore County.",
            "Iowa Environmental Mesonet BWI ASOS hourly wind observations, 2019-2024.",
        ],
    }

    generate_presentation_assets(context)
    return context


def generate_presentation_assets(context):
    _ensure_output()
    _plot_study_area(context)
    _plot_method_flow()
    _plot_emissions_summary(context)
    if context["overall_summary"]:
        _plot_pm25_summary(context)
        _plot_monitor_deltas(context)
        _plot_seasonal_summary(context)
        _plot_confounders(context)


def _plot_study_area(context):
    path = os.path.join(CACHE_DIR, PRESENTATION_IMAGES["study_area"])
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), dpi=150)
    regional_ax, city_ax = axes

    neighborhood_rows = []
    for name, info in NEIGHBORHOODS.items():
        if info["near_wheelabrator"] and info["near_i95"]:
            group = "Near both"
        elif info["near_i95"]:
            group = "I-95 only"
        else:
            group = "Control"
        neighborhood_rows.append({"name": name, "group": group, **info})
    neighborhoods_df = pd.DataFrame(neighborhood_rows)
    monitors_df = pd.DataFrame(context["monitor_summary"])

    for ax, xlim, ylim, title in [
        (
            regional_ax,
            (-76.9, -76.1),
            (39.05, 39.55),
            "Regional study design",
        ),
        (
            city_ax,
            (-76.70, -76.42),
            (39.20, 39.50),
            "Baltimore monitor area",
        ),
    ]:
        ax.set_facecolor("#f8f5ef")
        ax.plot(
            [point[1] for point in I95_WAYPOINTS],
            [point[0] for point in I95_WAYPOINTS],
            color="#d88c2d",
            linewidth=2.5,
            label="I-95 corridor",
            zorder=1,
        )
        for group, color in GROUP_COLORS.items():
            subset = neighborhoods_df[neighborhoods_df["group"] == group]
            ax.scatter(
                subset["lon"],
                subset["lat"],
                s=70,
                color=color,
                edgecolor="white",
                linewidth=0.9,
                label=group,
                zorder=3,
            )
        ax.scatter(
            WHEELABRATOR["lon"],
            WHEELABRATOR["lat"],
            s=180,
            marker="*",
            color="#7b1e1e",
            edgecolor="white",
            linewidth=1.0,
            label="Wheelabrator",
            zorder=4,
        )
        if not monitors_df.empty:
            ax.scatter(
                monitors_df["lon"],
                monitors_df["lat"],
                s=90,
                marker="^",
                color="#2f6690",
                edgecolor="white",
                linewidth=0.9,
                label="PM2.5 monitor",
                zorder=5,
            )
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        ax.set_title(title, fontsize=13, fontweight="bold")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.grid(alpha=0.2, linestyle="--")

    if not monitors_df.empty:
        for _, row in monitors_df.iterrows():
            city_ax.annotate(
                row["site_name"],
                (row["lon"], row["lat"]),
                xytext=(6, 5),
                textcoords="offset points",
                fontsize=8,
                color="#203246",
            )

    regional_ax.legend(loc="lower right", frameon=True, fontsize=8)
    fig.suptitle("Study areas, facility, and PM2.5 monitors", fontsize=16, fontweight="bold", y=0.98)
    fig.text(
        0.5,
        0.02,
        "Red neighborhoods are near both sources, orange neighborhoods represent the highway baseline, and gray neighborhoods are controls.",
        ha="center",
        fontsize=10,
        color="#4d4d4d",
    )
    fig.tight_layout(rect=[0, 0.05, 1, 0.95])
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _plot_method_flow():
    path = os.path.join(CACHE_DIR, PRESENTATION_IMAGES["workflow"])
    fig, ax = plt.subplots(figsize=(16, 3.4), dpi=150)
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    boxes = [
        (0.08, "EPA emissions\n2014 / 2017", "#e8d8c3"),
        (0.28, "BWI hourly wind\n2019-2024", "#cfe0ec"),
        (0.48, "AQS PM2.5 daily\nmonitor data", "#d6ead8"),
        (0.70, "Daily downwind\nclassification", "#f3dfc1"),
        (0.92, "Source comparison\nand conclusions", "#e4d7ef"),
    ]

    for x, label, color in boxes:
        ax.text(
            x,
            0.55,
            label,
            ha="center",
            va="center",
            fontsize=13,
            fontweight="bold",
            color="#2b2b2b",
            bbox=dict(boxstyle="round,pad=0.75", facecolor=color, edgecolor="#3b3b3b", linewidth=1.2),
        )

    for start, end in [(0.14, 0.22), (0.34, 0.42), (0.54, 0.64), (0.76, 0.86)]:
        ax.annotate(
            "",
            xy=(end, 0.55),
            xytext=(start, 0.55),
            arrowprops=dict(arrowstyle="->", linewidth=2, color="#6b7280"),
        )

    ax.text(
        0.5,
        0.08,
        "Each monitor-day was assigned to Wheelabrator only, I-95 only, both, or neither based on the dominant wind direction.",
        ha="center",
        fontsize=11,
        color="#4b5563",
    )
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _plot_emissions_summary(context):
    path = os.path.join(CACHE_DIR, PRESENTATION_IMAGES["emissions"])
    fig, axes = plt.subplots(2, 1, figsize=(12, 9), dpi=150)
    major_ax, trace_ax = axes

    major = pd.DataFrame(context["major_pollutants"])
    trace = pd.DataFrame(context["trace_pollutants"])
    x_major = np.arange(len(major))
    x_trace = np.arange(len(trace))
    width = 0.36

    major_ax.bar(x_major - width / 2, major["tons_2014"], width=width, color="#6c97b5", label="2014")
    major_ax.bar(x_major + width / 2, major["tons_2017"], width=width, color="#bf3f34", label="2017")
    major_ax.set_xticks(x_major)
    major_ax.set_xticklabels(major["pollutant"], fontsize=10)
    major_ax.set_ylabel("Tons per year")
    major_ax.set_title("Major pollutants", fontsize=14, fontweight="bold")
    major_ax.grid(axis="y", alpha=0.2)
    major_ax.legend(frameon=False)

    trace_ax.bar(x_trace - width / 2, trace["lbs_2014"], width=width, color="#6c97b5", label="2014")
    trace_ax.bar(x_trace + width / 2, trace["lbs_2017"], width=width, color="#bf3f34", label="2017")
    trace_ax.set_xticks(x_trace)
    trace_ax.set_xticklabels(trace["pollutant"], fontsize=10)
    trace_ax.set_ylabel("Pounds per year")
    trace_ax.set_title("Trace pollutants and metals", fontsize=14, fontweight="bold")
    trace_ax.grid(axis="y", alpha=0.2)

    fig.suptitle("Wheelabrator reported emissions", fontsize=18, fontweight="bold", y=0.98)
    fig.text(
        0.5,
        0.02,
        f"Total reported emissions rose from {context['emissions_headlines']['total_lbs_2014']:,} lbs in 2014 "
        f"to {context['emissions_headlines']['total_lbs_2017']:,} lbs in 2017 ({context['emissions_headlines']['total_pct_change']:+.1f}%).",
        ha="center",
        fontsize=11,
        color="#4b5563",
    )
    fig.tight_layout(rect=[0, 0.05, 1, 0.95])
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _plot_pm25_summary(context):
    path = os.path.join(CACHE_DIR, PRESENTATION_IMAGES["pm25_summary"])
    summary = pd.DataFrame(context["overall_summary"])
    fig, ax = plt.subplots(figsize=(11, 6), dpi=150)
    bars = ax.bar(
        summary["category"],
        summary["mean"],
        color=[CATEGORY_COLORS[cat] for cat in summary["category"]],
        width=0.62,
    )
    ax.set_ylabel("Mean PM2.5 (ug/m3)")
    ax.set_title("Average PM2.5 by downwind category", fontsize=17, fontweight="bold")
    ax.grid(axis="y", alpha=0.2)
    ax.set_axisbelow(True)
    for bar, (_, row) in zip(bars, summary.iterrows()):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.12,
            f"{row['mean']:.2f}\nn={row['count']}",
            ha="center",
            va="bottom",
            fontsize=10,
            color="#25303b",
        )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.text(
        0.5,
        0.02,
        "Values use one deduplicated PM2.5 reading per monitor-day before merging with the wind classification.",
        ha="center",
        fontsize=10,
        color="#4b5563",
    )
    fig.tight_layout(rect=[0, 0.05, 1, 0.95])
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _plot_monitor_deltas(context):
    path = os.path.join(CACHE_DIR, PRESENTATION_IMAGES["monitor_delta"])
    summary = pd.DataFrame(context["monitor_summary"])
    summary = summary[summary["wb_vs_i95_pct"].notna()].sort_values("wb_vs_i95_pct")
    fig, ax = plt.subplots(figsize=(11, 6), dpi=150)
    colors = ["#2f6690" if value < 0 else "#bf3f34" for value in summary["wb_vs_i95_pct"]]
    bars = ax.barh(summary["site_name"], summary["wb_vs_i95_pct"], color=colors, height=0.6)
    ax.axvline(0, color="#6b7280", linewidth=1)
    ax.set_xlabel("Percent difference: Wheelabrator-only vs I-95-only mean PM2.5")
    ax.set_title("Monitor-by-monitor Wheelabrator signal", fontsize=17, fontweight="bold")
    ax.grid(axis="x", alpha=0.2)
    ax.set_axisbelow(True)
    for bar, (_, row) in zip(bars, summary.iterrows()):
        text = f"{row['wb_mean']:.2f} vs {row['i95_mean']:.2f} ug/m3"
        offset = 2 if row["wb_vs_i95_pct"] >= 0 else -2
        align = "left" if row["wb_vs_i95_pct"] >= 0 else "right"
        ax.text(
            row["wb_vs_i95_pct"] + offset,
            bar.get_y() + bar.get_height() / 2,
            f"{_format_pct(row['wb_vs_i95_pct'])}  |  {text}",
            va="center",
            ha=align,
            fontsize=10,
            color="#25303b",
        )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _plot_seasonal_summary(context):
    path = os.path.join(CACHE_DIR, PRESENTATION_IMAGES["seasonal_summary"])
    seasonal = pd.DataFrame(context["seasonal_summary"])
    season_order = ["Winter", "Spring", "Summer", "Fall"]
    fig, ax = plt.subplots(figsize=(11, 6), dpi=150)
    for category in CATEGORY_ORDER:
        ax.plot(
            season_order,
            seasonal[category],
            marker="o",
            linewidth=2.5,
            markersize=7,
            color=CATEGORY_COLORS[category],
            label=category,
        )
    ax.set_ylabel("Mean PM2.5 (ug/m3)")
    ax.set_title("Seasonal PM2.5 pattern by downwind category", fontsize=17, fontweight="bold")
    ax.grid(alpha=0.2)
    ax.legend(frameon=False, ncol=2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.text(
        0.5,
        0.02,
        "Summer PM2.5 is elevated across every category, while spring, fall, and winter show a clearer Wheelabrator-only vs I-95-only gap.",
        ha="center",
        fontsize=10,
        color="#4b5563",
    )
    fig.tight_layout(rect=[0, 0.05, 1, 0.95])
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _plot_confounders(context):
    path = os.path.join(CACHE_DIR, PRESENTATION_IMAGES["confounders"])
    confounders = pd.DataFrame(context["confounders"]["rows"])
    if confounders.empty:
        return

    confounders = confounders.sort_values("regional_share_pct", na_position="first")

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), dpi=150)
    offset_ax, share_ax = axes

    offset_ax.barh(
        confounders["site_name"],
        confounders["angular_offset_deg"],
        color="#7a5c99",
        height=0.55,
    )
    offset_ax.axvline(45, color="#bf3f34", linestyle="--", linewidth=1.2)
    offset_ax.set_xlabel("Angular offset between bearings (degrees)")
    offset_ax.set_title("Wheelabrator vs I-95 bearing overlap", fontsize=13, fontweight="bold")
    offset_ax.grid(axis="x", alpha=0.2)
    offset_ax.set_axisbelow(True)
    for y, (_, row) in enumerate(confounders.iterrows()):
        offset_ax.text(
            row["angular_offset_deg"] + 1.5,
            y,
            f"WB {row['bearing_to_wheelabrator']:.0f}°  |  I-95 {row['bearing_to_i95']:.0f}°",
            va="center",
            fontsize=9,
            color="#25303b",
        )
    offset_ax.spines["top"].set_visible(False)
    offset_ax.spines["right"].set_visible(False)

    shares = confounders["regional_share_pct"].fillna(0)
    share_ax.barh(confounders["site_name"], shares, color="#bf3f34", height=0.55)
    share_ax.set_xlabel("Percent of Wheelabrator-only days with SW-quadrant wind (180-270°)")
    share_ax.set_title("Regional transport share of WB-only days", fontsize=13, fontweight="bold")
    share_ax.set_xlim(0, max(100, shares.max() + 10))
    share_ax.grid(axis="x", alpha=0.2)
    share_ax.set_axisbelow(True)
    for y, (_, row) in enumerate(confounders.iterrows()):
        if row["regional_share_pct"] is None or pd.isna(row["regional_share_pct"]):
            label = "n/a"
        else:
            label = f"{row['regional_share_pct']:.0f}%  (n={row['regional_n']}/{row['wb_only_n']})"
        share_ax.text(
            (row["regional_share_pct"] or 0) + 1.5,
            y,
            label,
            va="center",
            fontsize=9,
            color="#25303b",
        )
    share_ax.spines["top"].set_visible(False)
    share_ax.spines["right"].set_visible(False)

    fig.suptitle(
        "Directional confounders: overlap and regional transport",
        fontsize=16,
        fontweight="bold",
        y=0.99,
    )
    fig.text(
        0.5,
        0.02,
        "When the two bearings are close (dashed line = 45° tolerance) the WB-only and I-95-only categories are near-twins. "
        "High SW-quadrant share means many WB-only days are also Ohio Valley transport days.",
        ha="center",
        fontsize=10,
        color="#4b5563",
    )
    fig.tight_layout(rect=[0, 0.05, 1, 0.95])
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
