"""
Visualization suite for Baltimore air quality analysis.

Generates:
1. Wind rose for BWI station
2. Pollution rose (AQ by wind direction)
3. Directional comparison bar charts
4. Interactive Folium map with facility, monitors, I-95, neighborhoods
5. Time series plots
"""

import os
import math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm
from windrose import WindroseAxes
import folium
from folium.plugins import HeatMap
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from src.config import (
    WHEELABRATOR, I95_WAYPOINTS, NEIGHBORHOODS, OUTPUT_DIR,
)


def ensure_output():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── 1. Wind Rose ──

def plot_wind_rose(wind_df, title="BWI Wind Rose", filename="wind_rose.png"):
    """Standard wind rose showing wind direction and speed distribution."""
    ensure_output()
    df = wind_df.dropna(subset=["wind_dir", "wind_speed_ms"])

    fig = plt.figure(figsize=(10, 10))
    ax = WindroseAxes.from_ax(fig=fig)
    ax.bar(
        df["wind_dir"].values,
        df["wind_speed_ms"].values,
        normed=True,
        opening=0.8,
        edgecolor="white",
        bins=np.arange(0, 16, 2),
        cmap=cm.viridis,
    )
    ax.set_title(title, fontsize=16, pad=20)
    ax.set_legend(title="Wind Speed (m/s)", loc="lower right")

    path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved wind rose to {path}")
    return path


def plot_seasonal_wind_roses(wind_df, filename_prefix="wind_rose"):
    """Wind roses broken down by season."""
    ensure_output()
    df = wind_df.copy()
    df["month"] = df["timestamp"].dt.month
    df["season"] = df["month"].map({
        12: "Winter", 1: "Winter", 2: "Winter",
        3: "Spring", 4: "Spring", 5: "Spring",
        6: "Summer", 7: "Summer", 8: "Summer",
        9: "Fall", 10: "Fall", 11: "Fall",
    })

    paths = []
    for season in ["Winter", "Spring", "Summer", "Fall"]:
        subset = df[df["season"] == season].dropna(subset=["wind_dir", "wind_speed_ms"])
        if len(subset) < 10:
            continue
        path = plot_wind_rose(subset, title=f"BWI Wind Rose: {season}", filename=f"{filename_prefix}_{season.lower()}.png")
        paths.append(path)
    return paths


# ── 2. Pollution Rose ──

def plot_pollution_rose(merged_df, value_col="arithmetic_mean", pollutant="PM2.5",
                        filename="pollution_rose.png"):
    """
    Pollution rose: shows mean pollutant concentration by wind direction.
    Each petal length = mean concentration when wind blows from that direction.
    """
    ensure_output()
    df = merged_df.dropna(subset=["mean_wind_dir", value_col])

    # Bin wind directions into 16 sectors
    n_sectors = 16
    bin_width = 360 / n_sectors
    df = df.copy()
    df["dir_bin"] = ((df["mean_wind_dir"] + bin_width / 2) % 360 // bin_width).astype(int)

    sector_stats = df.groupby("dir_bin")[value_col].agg(["mean", "median", "count"]).reset_index()
    sector_stats["angle"] = sector_stats["dir_bin"] * bin_width

    fig = go.Figure()
    fig.add_trace(go.Barpolar(
        r=sector_stats["mean"],
        theta=sector_stats["angle"],
        width=[bin_width] * len(sector_stats),
        marker_color=sector_stats["mean"],
        marker_colorscale="YlOrRd",
        marker_line_color="white",
        marker_line_width=1,
        text=[f"Dir: {a:.0f}°<br>Mean: {m:.1f}<br>n={n}" for a, m, n in
              zip(sector_stats["angle"], sector_stats["mean"], sector_stats["count"])],
        hoverinfo="text",
    ))

    fig.update_layout(
        title=f"{pollutant} Pollution Rose: Mean Concentration by Wind Direction",
        polar=dict(
            angularaxis=dict(direction="clockwise", rotation=90),
            radialaxis=dict(showticklabels=True),
        ),
        width=700, height=700,
        showlegend=False,
    )

    path = os.path.join(OUTPUT_DIR, filename)
    fig.write_html(path.replace(".png", ".html"))
    print(f"Saved pollution rose to {path.replace('.png', '.html')}")
    return path.replace(".png", ".html")


# ── 3. Directional Comparison ──

def plot_directional_comparison(analysis_results, pollutant="PM2.5",
                                filename="directional_comparison.html"):
    """Bar chart comparing pollutant levels: downwind WB vs I-95 vs neither."""
    ensure_output()

    categories = ["only_wheelabrator", "only_i95", "both", "neither"]
    labels = [analysis_results[c]["label"] for c in categories]
    means = [analysis_results[c]["mean"] or 0 for c in categories]
    medians = [analysis_results[c]["median"] or 0 for c in categories]
    n_days = [analysis_results[c]["n_days"] for c in categories]
    p90s = [analysis_results[c]["p90"] or 0 for c in categories]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Mean", x=labels, y=means, text=[f"n={n}" for n in n_days], textposition="outside"))
    fig.add_trace(go.Bar(name="Median", x=labels, y=medians))
    fig.add_trace(go.Bar(name="90th Percentile", x=labels, y=p90s))

    fig.update_layout(
        title=f"{pollutant}: Concentration by Wind Direction Category",
        yaxis_title=f"{pollutant} Concentration (µg/m³)",
        barmode="group",
        width=900, height=500,
    )

    path = os.path.join(OUTPUT_DIR, filename)
    fig.write_html(path)
    print(f"Saved directional comparison to {path}")
    return path


def plot_seasonal_comparison(seasonal_results, pollutant="PM2.5",
                             filename="seasonal_comparison.html"):
    """Seasonal breakdown of directional analysis."""
    ensure_output()

    fig = make_subplots(rows=2, cols=2, subplot_titles=["Winter", "Spring", "Summer", "Fall"])

    for i, season in enumerate(["Winter", "Spring", "Summer", "Fall"]):
        row, col = i // 2 + 1, i % 2 + 1
        results = seasonal_results[season]
        categories = ["only_wheelabrator", "only_i95", "both", "neither"]
        labels = ["WB only", "I-95 only", "Both", "Neither"]
        means = [results[c]["mean"] or 0 for c in categories]
        n_days = [results[c]["n_days"] for c in categories]

        fig.add_trace(go.Bar(
            x=labels, y=means,
            text=[f"n={n}" for n in n_days], textposition="outside",
            name=season, showlegend=(i == 0),
        ), row=row, col=col)

    fig.update_layout(
        title=f"{pollutant}: Seasonal Directional Comparison",
        height=600, width=900,
    )

    path = os.path.join(OUTPUT_DIR, filename)
    fig.write_html(path)
    print(f"Saved seasonal comparison to {path}")
    return path


# ── 4. Interactive Map ──

def create_map(monitors_df=None, filename="baltimore_air_map.html"):
    """
    Interactive Folium map showing Wheelabrator, I-95 corridor,
    AQS monitors, and neighborhoods.
    """
    ensure_output()

    m = folium.Map(
        location=[WHEELABRATOR["lat"], WHEELABRATOR["lon"]],
        zoom_start=13,
        tiles="CartoDB positron",
    )

    # Wheelabrator marker
    folium.Marker(
        [WHEELABRATOR["lat"], WHEELABRATOR["lon"]],
        popup=folium.Popup(
            f"<b>{WHEELABRATOR['name']}</b><br>{WHEELABRATOR['address']}<br>Stack height: {WHEELABRATOR['stack_height_m']}m",
            max_width=300,
        ),
        icon=folium.Icon(color="red", icon="industry", prefix="fa"),
        tooltip="Wheelabrator Baltimore",
    ).add_to(m)

    # I-95 corridor
    folium.PolyLine(
        I95_WAYPOINTS,
        color="orange",
        weight=5,
        opacity=0.8,
        tooltip="I-95 Corridor",
    ).add_to(m)

    # Neighborhoods
    for name, info in NEIGHBORHOODS.items():
        color = "red" if info["near_wheelabrator"] and info["near_i95"] else \
                "orange" if info["near_i95"] else \
                "purple" if info["near_wheelabrator"] else "gray"

        tags = []
        if info["near_wheelabrator"]:
            tags.append("Near Wheelabrator")
        if info["near_i95"]:
            tags.append("Near I-95")
        if not tags:
            tags.append("Control area")

        folium.CircleMarker(
            [info["lat"], info["lon"]],
            radius=8,
            color=color,
            fill=True,
            fill_opacity=0.6,
            popup=f"<b>{name}</b><br>{', '.join(tags)}",
            tooltip=name,
        ).add_to(m)

    # AQS monitors (if data provided)
    if monitors_df is not None and not monitors_df.empty:
        for _, row in monitors_df.iterrows():
            if "latitude" in row and "longitude" in row:
                dist = row.get("dist_from_wheelabrator_km", "?")
                pollutant = row.get("pollutant", "?")
                site = row.get("site_number", "?")
                folium.Marker(
                    [row["latitude"], row["longitude"]],
                    popup=f"<b>AQS Monitor {site}</b><br>Pollutant: {pollutant}<br>Dist from WB: {dist:.1f} km",
                    icon=folium.Icon(color="blue", icon="cloud", prefix="fa"),
                    tooltip=f"Monitor: {pollutant}",
                ).add_to(m)

    # Legend
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
                background: white; padding: 12px; border-radius: 8px;
                border: 2px solid #ccc; font-size: 13px;">
        <b>Legend</b><br>
        <i class="fa fa-industry" style="color:red"></i> Wheelabrator/WIN Waste<br>
        <span style="color:orange">━━</span> I-95 Corridor<br>
        <span style="color:red">●</span> Near both WB & I-95<br>
        <span style="color:orange">●</span> Near I-95 only<br>
        <span style="color:purple">●</span> Near Wheelabrator only<br>
        <span style="color:gray">●</span> Control area<br>
        <i class="fa fa-cloud" style="color:blue"></i> AQS Monitor
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    path = os.path.join(OUTPUT_DIR, filename)
    m.save(path)
    print(f"Saved map to {path}")
    return path


# ── 5. Time Series ──

def plot_time_series(merged_df, value_col="arithmetic_mean", pollutant="PM2.5",
                     filename="time_series.html"):
    """Time series of pollutant colored by downwind status."""
    ensure_output()
    df = merged_df.dropna(subset=[value_col]).copy()

    df["category"] = "Neither"
    df.loc[
        (df["pct_downwind_wheelabrator"] > 0.5) & (df["pct_downwind_i95"] > 0.5),
        "category"
    ] = "Both"
    df.loc[
        (df["pct_downwind_wheelabrator"] > 0.5) & (df["pct_downwind_i95"] <= 0.5),
        "category"
    ] = "Wheelabrator only"
    df.loc[
        (df["pct_downwind_wheelabrator"] <= 0.5) & (df["pct_downwind_i95"] > 0.5),
        "category"
    ] = "I-95 only"

    color_map = {
        "Wheelabrator only": "#d62728",
        "I-95 only": "#ff7f0e",
        "Both": "#9467bd",
        "Neither": "#7f7f7f",
    }

    fig = px.scatter(
        df, x="date_local", y=value_col, color="category",
        color_discrete_map=color_map,
        opacity=0.4,
        title=f"{pollutant} Daily Values: Colored by Downwind Category",
        labels={value_col: f"{pollutant} (µg/m³)", "date_local": "Date"},
    )

    # Add rolling average
    df_sorted = df.sort_values("date_local")
    for cat in ["Wheelabrator only", "I-95 only", "Neither"]:
        subset = df_sorted[df_sorted["category"] == cat].copy()
        if len(subset) > 30:
            subset["rolling"] = subset[value_col].rolling(30, center=True).mean()
            fig.add_trace(go.Scatter(
                x=subset["date_local"], y=subset["rolling"],
                mode="lines", name=f"{cat} (30-day avg)",
                line=dict(color=color_map.get(cat, "gray"), width=2),
            ))

    fig.update_layout(width=1200, height=500)

    path = os.path.join(OUTPUT_DIR, filename)
    fig.write_html(path)
    print(f"Saved time series to {path}")
    return path


# ── 6. Facility Emissions ──

def plot_facility_emissions(emissions_df, filename="facility_emissions.html"):
    """
    Bar chart comparing Wheelabrator emissions across years and pollutants.
    Uses compiled NEI data from fetch_emissions.py.
    """
    ensure_output()

    if emissions_df is None or emissions_df.empty:
        print("No emissions data to plot")
        return None

    # Major pollutants (tons/year scale)
    major = emissions_df[emissions_df["tons_per_year"] > 1].copy()

    fig = px.bar(
        major, x="pollutant", y="tons_per_year", color="year",
        barmode="group",
        title="Wheelabrator Baltimore: Reported Emissions by Pollutant (EPA NEI)",
        labels={"tons_per_year": "Tons per Year", "pollutant": "Pollutant", "year": "Year"},
        color_discrete_sequence=["#2196F3", "#F44336"],
    )
    fig.update_layout(width=1000, height=500, xaxis_tickangle=-45)

    path = os.path.join(OUTPUT_DIR, filename)
    fig.write_html(path)
    print(f"Saved emissions chart to {path}")

    # Also make a chart for trace pollutants (lbs scale)
    trace = emissions_df[emissions_df["tons_per_year"] <= 1].copy()
    if not trace.empty:
        fig2 = px.bar(
            trace, x="pollutant", y="lbs_per_year", color="year",
            barmode="group",
            title="Wheelabrator Baltimore: Trace Pollutant Emissions (EPA NEI)",
            labels={"lbs_per_year": "Pounds per Year", "pollutant": "Pollutant", "year": "Year"},
            color_discrete_sequence=["#2196F3", "#F44336"],
        )
        fig2.update_layout(width=800, height=400, xaxis_tickangle=-45)
        path2 = os.path.join(OUTPUT_DIR, "facility_emissions_trace.html")
        fig2.write_html(path2)
        print(f"Saved trace emissions chart to {path2}")

    return path
