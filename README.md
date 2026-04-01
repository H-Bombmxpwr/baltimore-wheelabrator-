# Baltimore Air Quality Analysis

Analyzing the impact of **Wheelabrator Baltimore (WIN Waste)** — Baltimore's largest stationary air pollution source — on local air quality, compared to pollution from the **I-95 corridor**.

The project collects wind, emissions, and air quality monitoring data, then uses wind direction analysis to determine whether neighborhoods downwind of the incinerator experience worse air quality than those downwind of I-95 traffic.

## Key Question

> Is air quality worse in neighborhoods downwind of the Wheelabrator waste-to-energy incinerator versus downwind of I-95?

## How It Works

1. **Wind data** is fetched from the Iowa Environmental Mesonet (BWI airport station, 2019-2024) to establish prevailing wind patterns.
2. **Facility emissions** are sourced from the EPA National Emissions Inventory (NEI) — NOx, SO2, PM2.5, heavy metals, and more.
3. **Air quality readings** are pulled from EPA AQS monitoring stations across Baltimore City and County.
4. **Directional analysis** classifies each day by whether monitors were downwind of Wheelabrator, I-95, both, or neither, then compares pollutant concentrations across those categories.
5. **Visualizations** are generated as interactive HTML charts (Plotly, Folium) and wind rose PNGs.

## Project Structure

```
baltimore-air/
├── run_all.py              # Main pipeline orchestrator
├── app.py                  # Flask web server for the dashboard
├── requirements.txt        # Python dependencies
├── .env.example            # Template for EPA AQS API credentials
├── src/
│   ├── config.py           # Facility locations, neighborhoods, parameters
│   ├── fetch_wind.py       # Wind data from Iowa Mesonet (no API key)
│   ├── fetch_emissions.py  # EPA NEI emissions (compiled data)
│   ├── fetch_tri.py        # Toxics Release Inventory via EPA Envirofacts
│   ├── fetch_aqs.py        # EPA AQS air quality monitors (requires API key)
│   ├── analyze.py          # Directional and temporal analysis
│   └── visualize.py        # Charts, maps, and wind roses
├── data/                   # Cached data files
├── output/                 # Generated HTML charts and PNG wind roses
├── templates/              # Flask dashboard template
└── notebooks/              # Jupyter notebooks for exploration
```

## Setup

```bash
# Clone and enter the project
git clone <repo-url>
cd baltimore-air

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

### API Key (optional but recommended)

The full analysis requires a free EPA AQS API key. Register at https://aqs.epa.gov/data/api/signup and then create a `.env` file:

```
AQS_EMAIL=your_email@example.com
AQS_KEY=your_key_here
```

Wind and emissions analysis works without an API key.

## Usage

### Run the analysis pipeline

```bash
# Full pipeline (requires AQS API key in .env)
python run_all.py

# Wind data + wind roses only (no API key needed)
python run_all.py --wind-only

# Everything except AQS data (emissions + wind, no API key needed)
python run_all.py --no-aqs
```

Output files are written to `output/`.

### View results in the web dashboard

```bash
python app.py
```

Open http://localhost:5000 to browse all visualizations.

## Output

| File | Description |
|------|-------------|
| `baltimore_air_map.html` | Interactive Folium map with facility, I-95 route, neighborhoods, and monitors |
| `facility_emissions.html` | Wheelabrator emissions by pollutant (2014 vs 2017) |
| `facility_emissions_trace.html` | Trace pollutants: lead, mercury, nickel, chromium VI |
| `wind_rose.png` | Overall wind direction/speed distribution |
| `wind_rose_{season}.png` | Seasonal wind roses (winter, spring, summer, fall) |
| `pollution_rose_*.html` | Pollutant concentration by wind direction (per monitor) |
| `directional_*.html` | Wheelabrator vs I-95 downwind comparison (per monitor) |
| `timeseries_*.html` | Time series colored by downwind category |
| `seasonal_*.html` | Seasonal directional breakdowns |

## Data Sources

- **Wind**: [Iowa Environmental Mesonet](https://mesonet.agron.iastate.edu/) — BWI ASOS station, hourly observations
- **Emissions**: [EPA National Emissions Inventory](https://www.epa.gov/air-emissions-inventories/national-emissions-inventory-nei) — 2014, 2017
- **Air Quality**: [EPA Air Quality System (AQS)](https://aqs.epa.gov/aqsweb/documents/data_api.html) — daily PM2.5, PM10, SO2, NO2, ozone, CO
- **Toxics**: [EPA Toxics Release Inventory](https://www.epa.gov/toxics-release-inventory-tri-program) via Envirofacts API

## Neighborhoods Studied

The study compares three groups to isolate Wheelabrator's impact from general highway pollution:

**Near both Wheelabrator & I-95** — neighborhoods exposed to the incinerator *and* highway traffic:

| Neighborhood | Near Wheelabrator | Near I-95 |
|-------------|:-:|:-:|
| Westport | Yes | Yes |
| Cherry Hill | Yes | Yes |
| Brooklyn | Yes | Yes |
| Curtis Bay | Yes | Yes |
| South Baltimore | Yes | Yes |
| Federal Hill | Yes | Yes |

**I-95 corridor only** — communities along I-95 but far from Wheelabrator, serving as the highway-pollution baseline:

| Neighborhood | Near Wheelabrator | Near I-95 |
|-------------|:-:|:-:|
| Elkridge (south) | No | Yes |
| Savage (south) | No | Yes |
| Laurel (south) | No | Yes |
| Rossville (north) | No | Yes |
| White Marsh (north) | No | Yes |
| Aberdeen (north) | No | Yes |

**Control** — neighborhoods away from both sources:

| Neighborhood | Near Wheelabrator | Near I-95 |
|-------------|:-:|:-:|
| Canton | No | No |
| Fells Point | No | No |
| Dundalk | No | No |
| Hampden | No | No |

## License

This project is for research and educational purposes.
