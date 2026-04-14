# Baltimore Air Quality Analysis

Directional analysis of **Wheelabrator Baltimore (WIN Waste)** — Baltimore's largest stationary air-pollution source — against the I-95 corridor background. The project collects wind, emissions, and EPA AQS monitor data, then uses wind-direction classification to ask whether PM2.5 is higher on days when monitors are downwind of the incinerator than on days when they are downwind of the highway alone.

A companion narrative presentation sits on top of the dashboard at `/presentation` and walks through the same evidence with explicit stress-tests for the main confounders.

## Key Question

> Was ambient PM2.5 higher when Baltimore-area monitors were downwind of Wheelabrator than when they were downwind of the I-95 corridor alone — and can that gap be separated from regional southwesterly transport?

## What's in this Repo

This repo is split into three layers:

1. **Data acquisition** — `src/fetch_*.py` modules that pull from Iowa Mesonet, the EPA NEI, the EPA GHG Reporting Program, and the EPA AQS API, and cache the results under `data/`.
2. **Analysis** — `src/analyze.py` for bearings, line-source projection, directional classification, and aggregation, plus `src/presentation.py` for the presentation-level rollup and confounder stress-test.
3. **Presentation** — `src/visualize.py` writes the interactive charts and wind-rose PNGs; `app.py` serves a Flask dashboard and a 13-slide presentation deck; `build.py` freezes everything into `docs/` for GitHub Pages.

## Pipeline (Data Order)

```
  ┌─ Iowa Mesonet ASOS (BWI)           ─┐
  │    src/fetch_wind.py                │
  │    → data/wind_bwi.csv              │
  │                                     │
  ├─ EPA NEI 2014 + 2017 (inline)       ├─►  src/analyze.py
  │    src/fetch_emissions.py           │      ├─ classify_wind_for_monitor  (bearing ± 45°)
  │    → data/wheelabrator_emissions.csv│      ├─ classify_wind_for_i95       (line-source projection)
  │    → data/wheelabrator_ghg.csv      │      ├─ merge_aqi_wind              (hourly → daily shares)
  │                                     │      ├─ directional_analysis        (WB-only / I-95-only / Both / Neither)
  └─ EPA AQS API (PM2.5, PM10, SO2, ...)│      └─ seasonal_directional_analysis
       src/fetch_aqs.py                 │                   │
       → data/aqs_monitors.csv          │                   ▼
       → data/aqs_pm25.csv, aqs_so2...──┘        src/presentation.py
                                                   ├─ confounder stress-test
                                                   │    (bearing overlap + SW-quadrant share)
                                                   ├─ deck context + hero stats
                                                   └─ presentation_assets/*.png
                                                             │
                                                             ▼
                                                   src/visualize.py
                                                   ├─ output/wind_rose*.png
                                                   ├─ output/pollution_rose_*.html
                                                   ├─ output/directional_*.html
                                                   ├─ output/timeseries_*.html
                                                   └─ output/seasonal_*.html
                                                             │
                                                             ▼
                                                        app.py  /  build.py
                                                        (Flask → docs/)
```

### Step 1 — Hourly Wind (Iowa Environmental Mesonet)

- **Module:** `src/fetch_wind.py`
- **Source:** `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py` with `station=BWI`, `report_type=3` (routine METAR), `tz=UTC`, `format=onlycomma`, one request per calendar year between `DEFAULT_START_YEAR` and `DEFAULT_END_YEAR` (2019-2024).
- **Requested fields:** `drct`, `sknt`, `gust_sknt` (direction in meteorological convention — the direction wind *comes from* — plus sustained and gust speeds in knots).
- **On load:** speed is converted from knots to m/s, column names are lowercased, and rows are written to `data/wind_bwi.csv`.
- **No API key required.**

### Step 2 — Facility Emissions (EPA NEI + GHG Reporting Program)

- **Module:** `src/fetch_emissions.py`
- **Why inline:** NEI downloads are annual snapshots, so the 2014 and 2017 values for Wheelabrator are embedded as a `{year: {pollutant: lbs_per_year}}` dict.
- **GHG:** CO2-equivalent metric tons come from the EPA Greenhouse Gas Reporting Program, facility ID `1004094`.
- **Derived columns:** `tons_per_year = lbs_per_year / 2000`; long-form frames are written to `data/wheelabrator_emissions.csv` and `data/wheelabrator_ghg.csv`.
- **Used by:** the dashboard emissions tables/charts and the presentation deck's facility slide.

### Step 3 — AQS Monitor Data (EPA Air Quality System API)

- **Module:** `src/fetch_aqs.py`
- **Source:** `https://aqs.epa.gov/data/api` daily-summary endpoint. Requires free credentials in `.env` (`AQS_EMAIL`, `AQS_KEY`).
- **Scope:** Maryland FIPS `24`, Baltimore City county `510`, Baltimore County county `005`.
- **Pollutants:** parameter codes defined in `src/config.py:POLLUTANTS` — PM2.5 (`88101`), PM10 (`81102`), SO2 (`42401`), NO2 (`42602`), Ozone (`44201`), CO (`42101`).
- **Outputs:** `data/aqs_monitors.csv` (lat/lon + site metadata for discovered monitors) and one CSV per pollutant (`data/aqs_pm25.csv`, `data/aqs_so2.csv`, …).
- **Deduplication:** `src/presentation.py:_load_pm25_daily` collapses the PM2.5 frame to one value per `(latitude, longitude, date_local)` group by averaging `arithmetic_mean` and `aqi`. This happens *before* the merge with wind to avoid double-counting rows that share a monitor-day.

### Step 4 — Directional Classification (`src/analyze.py`)

For every AQS monitor, each hourly wind observation is classified against two reference bearings:

- **Wheelabrator (point source):** `classify_wind_for_monitor` computes `bearing_from(monitor_lat, monitor_lon, WHEELABRATOR.lat, WHEELABRATOR.lon)` and flags the hour as *downwind of WB* when `angle_diff(wind_dir, bearing_to_wb) ≤ 45°`. Meteorological convention matters here: `wind_dir` is the direction the wind comes *from*, so when `wind_dir ≈ bearing_to_wb` the plume is actually being carried toward the monitor.
- **I-95 (line source):** `classify_wind_for_i95` treats the highway as a polyline defined by `I95_WAYPOINTS` in `src/config.py`. `nearest_point_on_polyline` projects the monitor onto each segment, clamping the parameter `t` to `[0, 1]`, and picks the closest segment point. Bearing to that projected point (rather than to the nearest vertex) is what feeds the ±45° test. This avoids biasing the I-95 bearing toward whichever waypoint happened to be sampled.

Hourly flags are then aggregated to daily by `merge_aqi_wind`:

| Column | Source | Meaning |
|---|---|---|
| `mean_wind_speed_ms` | mean over day | average sustained speed |
| `mean_wind_dir` | `circular_mean` of hourly degrees | vector mean of direction |
| `pct_downwind_wheelabrator` | mean of hourly bool flags | share of hours downwind of WB |
| `pct_downwind_i95` | mean of hourly bool flags | share of hours downwind of I-95 |
| `n_wind_obs` | count | non-null hourly obs that day |

A day crosses into a category when its share exceeds 0.5:

| Category | `pct_downwind_wheelabrator` | `pct_downwind_i95` |
|---|:-:|:-:|
| **Wheelabrator only** | > 0.5 | ≤ 0.5 |
| **I-95 only**          | ≤ 0.5 | > 0.5 |
| **Both**               | > 0.5 | > 0.5 |
| **Neither**            | ≤ 0.5 | ≤ 0.5 |

`directional_analysis` computes mean / median / p90 PM2.5 inside each bucket; `seasonal_directional_analysis` does the same after tagging days with DJF / MAM / JJA / SON.

### Step 5 — Presentation Rollup + Confounder Stress-Test (`src/presentation.py`)

The presentation context builder (`get_presentation_context`) is the orchestration layer between `analyze.py` and the Jinja templates. It:

1. Loops over every AQS monitor with ≥ 30 merged monitor-days.
2. Builds a per-monitor row with means, deltas (`wb_vs_i95_pct`), nearest neighborhood, and distance to Wheelabrator.
3. Runs the **confounder stress-test**:
   - **Bearing overlap** — records `bearing_to_wheelabrator`, `bearing_to_i95`, and `angular_offset_deg` for each monitor so the reader can see how independent the two categories actually are at that site (offsets below the 45° tolerance mean the categories are near-twins).
   - **Regional-transport share** — counts what fraction of WB-only monitor-days had a daily mean wind direction in the 180°–270° (southwesterly) quadrant, which is the same quadrant that carries Ohio Valley and mid-Atlantic PM2.5 into Baltimore. Computed once per monitor and once across all monitors, for both the WB-only and I-95-only buckets.
4. Aggregates across monitors for the headline numbers (overall WB-only vs I-95-only delta, seasonal splits, positive-signal monitor count).
5. Calls `generate_presentation_assets`, which writes the static PNG figures (`presentation_assets/presentation_*.png`) used by the deck — including a new `presentation_confounders.png` that plots angular offset alongside regional-transport share per monitor.

Results are cached per process with `functools.lru_cache`.

### Step 6 — Visualization & Serving

- **`src/visualize.py`** emits:
  - Wind roses: `output/wind_rose.png` (overall) plus four seasonal PNGs via `plot_wind_rose` / `plot_seasonal_wind_roses` (matplotlib polar).
  - Facility charts: `output/facility_emissions.html`, `output/facility_emissions_trace.html` (Plotly).
  - Per-monitor interactive charts: `pollution_rose_<lat>_<lon>.html`, `directional_<lat>_<lon>.html`, `timeseries_<lat>_<lon>.html`, `seasonal_<lat>_<lon>.html` (Plotly).
  - Study map: Folium-backed Leaflet map rendered on demand by `app.py:study_map`.
- **`app.py`** is the Flask layer. Routes:
  - `/` — the technical dashboard (this repo's `templates/index.html`).
  - `/presentation` — the 13-slide narrative deck (`templates/presentation.html`).
  - `/study-map`, `/emissions`, `/emissions-trace`, `/wind-rose`, `/wind-rose/<season>` — cached artifacts.
  - `/output/<filename>` and `/presentation-assets/<filename>` — static serves.
  - `/api/emissions` — JSON emissions dump.
- **`build.py`** uses Flask's test client to render `/`, `/presentation`, and `/study-map` once, rewrites absolute paths to relative, and copies `output/` + `presentation_assets/` into `docs/` for GitHub Pages (with a `.nojekyll` marker).

## File Layout

```
baltimore-air/
├── app.py                     # Flask dashboard + presentation server
├── build.py                   # Static-site builder → docs/
├── run_all.py                 # End-to-end pipeline orchestrator
├── requirements.txt
├── .env.example               # AQS_EMAIL / AQS_KEY template
├── presentation_script.txt    # Speaker notes (13 slides)
├── src/
│   ├── config.py              # Facility & I-95 coords, neighborhood groups, tolerances
│   ├── fetch_wind.py          # Iowa Mesonet ASOS pull
│   ├── fetch_emissions.py     # Inline NEI + GHG values
│   ├── fetch_aqs.py           # EPA AQS API client + monitor discovery
│   ├── fetch_tri.py           # Toxics Release Inventory (auxiliary)
│   ├── analyze.py             # Bearings, line-source projection, directional classifier
│   ├── presentation.py        # Deck context builder + confounder stress-test
│   └── visualize.py           # Plotly charts, matplotlib wind roses, Folium map
├── data/                      # Cached CSVs (wind, emissions, GHG, per-pollutant AQS)
├── output/                    # Generated interactive HTML + PNG artifacts
├── presentation_assets/       # Static PNG figures for the deck
├── templates/
│   ├── index.html             # Dashboard (with inline "how this was built" notes)
│   └── presentation.html      # 13-slide deck
└── docs/                      # Built static site (GitHub Pages)
```

## Setup

```bash
git clone <repo-url>
cd baltimore-air

python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### EPA AQS API Key (required for the full pipeline)

Register at https://aqs.epa.gov/data/api/signup and create `.env`:

```
AQS_EMAIL=your_email@example.com
AQS_KEY=your_key_here
```

Wind + emissions + presentation work without an API key, as long as the cached `data/aqs_*.csv` files exist from a prior run.

## Usage

```bash
# Full pipeline (requires AQS API key)
python run_all.py

# Just wind data + wind roses (no API key)
python run_all.py --wind-only

# Everything except AQS data (no API key)
python run_all.py --no-aqs

# Serve dashboard + presentation locally
python app.py
# → http://localhost:5000          (dashboard)
# → http://localhost:5000/presentation

# Build static site into docs/ for GitHub Pages
python build.py
```

## Dashboard vs Presentation

The two surfaces serve different audiences and are intentionally styled differently:

- **Dashboard (`/`)** — the technical build log. Shows every data source, every intermediate table, and how each chart was produced. The inline "How this section is built" blocks describe the exact function calls and output paths. Use this when you want to understand *how* the analysis was produced or to debug a specific chart.
- **Presentation (`/presentation`)** — the narrative. A 13-slide deck that walks through the research question, the directional method, the emissions baseline, the wind patterns, the PM2.5 results, a confounder stress-test, and conclusions. Use this when you want the argument, not the plumbing.

The prominent gradient CTA at the top of the dashboard links directly to the deck.

## Honest Limitations

This is a screening analysis, not a source-attribution model. The confounder slide in the deck and the Limitations slide both call this out, but worth repeating here:

1. **Regional transport confound.** Most AQS monitors sit north and northeast of Wheelabrator, so "downwind of WB" ≈ "winds from the southwest" — the same winds that bring Ohio Valley and mid-Atlantic regional PM2.5 into Baltimore. The stress-test quantifies how much of the WB-only category falls inside that 180°–270° quadrant, and the answer is "a lot." Part of the raw WB-only vs I-95-only gap is regional transport, not local facility impact.
2. **Bearing overlap.** Even with the line-source projection for I-95, the bearing to Wheelabrator and the bearing to the nearest point on I-95 sit inside the 45° tolerance window for some monitors. The WB-only and I-95-only categories are not fully independent wind regimes at those sites.
3. **Single wind station.** All directional classification uses BWI, south of the city. Sea breezes, urban heat islands, and local terrain can bend the actual wind at each monitor.
4. **Daily averaging.** PM2.5 spikes on sub-daily timescales are smoothed out.
5. **Sparse fence-line coverage.** The AQS monitors that met the 30-day minimum are not sited in the closest fence-line neighborhoods (Westport, Cherry Hill, Curtis Bay).
6. **Inventory vs ambient mismatch.** Facility emissions are 2014 + 2017 NEI snapshots; the ambient PM2.5 analysis uses 2019-2024 monitor data.

Recommended next steps (also in the deck): fence-line monitors, regional-background subtraction (e.g. from an upwind rural site or a chemical-transport-model baseline), extending the method to SO2 / NO2 where the fingerprint is more local than PM2.5, and pairing with local wind fields or dispersion modeling.

## Data Sources

- **Wind** — [Iowa Environmental Mesonet](https://mesonet.agron.iastate.edu/) — BWI ASOS station, hourly observations.
- **Emissions** — [EPA National Emissions Inventory](https://www.epa.gov/air-emissions-inventories/national-emissions-inventory-nei), 2014 & 2017.
- **Greenhouse Gas** — [EPA Greenhouse Gas Reporting Program](https://www.epa.gov/ghgreporting), facility ID 1004094.
- **Air Quality** — [EPA Air Quality System (AQS)](https://aqs.epa.gov/aqsweb/documents/data_api.html) daily summaries for PM2.5, PM10, SO2, NO2, ozone, CO.
- **Toxics** — [EPA Toxics Release Inventory](https://www.epa.gov/toxics-release-inventory-tri-program) via Envirofacts API.

## Neighborhoods Studied (Framing)

The `NEIGHBORHOODS` dict in `src/config.py` defines three groups used to frame the geographic design on the dashboard and in the presentation. The numerical analysis itself runs over the four AQS monitors that fell inside the study area with sufficient coverage — it does **not** attach a measured value to every listed neighborhood. The neighborhoods are framing; the monitors are evidence.

**Near both Wheelabrator & I-95:** Westport, Cherry Hill, Brooklyn, Curtis Bay, South Baltimore, Federal Hill.

**I-95 corridor only (highway baseline):** Elkridge, Savage, Laurel (south of Baltimore); Rossville, White Marsh, Aberdeen (north).

**Control:** Canton, Fells Point, Dundalk, Hampden.

## License

Research and educational use.
