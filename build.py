"""
Build static site for GitHub Pages.

Renders the Flask app once and writes a fully self-contained
static site into docs/ that can be served by GitHub Pages.

Usage:  python build.py
Output: docs/ directory ready to deploy
"""

import os
import shutil

# Ensure we're running from the project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app import app

DOCS_DIR = "docs"
OUTPUT_SRC = "output"


def build():
    # Clean and create docs directory
    if os.path.exists(DOCS_DIR):
        shutil.rmtree(DOCS_DIR)
    os.makedirs(os.path.join(DOCS_DIR, "output"))

    with app.test_client() as client:
        # 1. Render the main dashboard (Jinja2 bakes in all data)
        print("Rendering index.html ...")
        resp = client.get("/")
        index_html = resp.data.decode("utf-8")

        # 2. Render the study map (Folium generates self-contained HTML)
        print("Rendering study-map.html ...")
        resp = client.get("/study-map")
        study_map_html = resp.data.decode("utf-8")

    # 3. Rewrite Flask route URLs to relative file paths
    #    Order matters: more specific patterns first
    replacements = [
        # Study map iframe
        ('src="/study-map"',         'src="study-map.html"'),
        # Emissions charts (trace first — it's more specific)
        ('src="/emissions-trace"',   'src="output/facility_emissions_trace.html"'),
        ('src="/emissions"',         'src="output/facility_emissions.html"'),
        # Seasonal wind roses (before generic /wind-rose)
        ('"/wind-rose/winter"',      '"output/wind_rose_winter.png"'),
        ('"/wind-rose/spring"',      '"output/wind_rose_spring.png"'),
        ('"/wind-rose/summer"',      '"output/wind_rose_summer.png"'),
        ('"/wind-rose/fall"',        '"output/wind_rose_fall.png"'),
        # Overall wind rose
        ('"/wind-rose"',             '"output/wind_rose.png"'),
        # Per-monitor chart iframes (remove leading slash)
        ('"/output/',                '"output/'),
    ]

    for old, new in replacements:
        index_html = index_html.replace(old, new)

    # 4. Write rendered HTML files
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    with open(os.path.join(DOCS_DIR, "study-map.html"), "w", encoding="utf-8") as f:
        f.write(study_map_html)

    # 5. Copy all output files (Plotly charts, wind rose PNGs)
    print("Copying output files ...")
    count = 0
    for fname in os.listdir(OUTPUT_SRC):
        src = os.path.join(OUTPUT_SRC, fname)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(DOCS_DIR, "output", fname))
            print(f"  {fname}")
            count += 1

    # 6. Add .nojekyll so GitHub Pages serves files as-is
    open(os.path.join(DOCS_DIR, ".nojekyll"), "w").close()

    print(f"\nDone! Static site built in {DOCS_DIR}/")
    print(f"  index.html")
    print(f"  study-map.html")
    print(f"  output/ ({count} files)")
    print(f"\nPreview locally:  python -m http.server 8000 -d {DOCS_DIR}")
    print(f"Then open:        http://localhost:8000")


if __name__ == "__main__":
    build()
