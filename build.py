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
PRESENTATION_SRC = "presentation_assets"


def rewrite_site_html(html):
    """Rewrite Flask URLs to relative paths for static hosting."""
    replacements = [
        ('href="/presentation"',    'href="presentation.html"'),
        ('href="/"',                'href="index.html"'),
        ('"/presentation-assets/',  '"presentation-assets/'),
        ('src="/study-map"',        'src="study-map.html"'),
        ('src="/emissions-trace"',  'src="output/facility_emissions_trace.html"'),
        ('src="/emissions"',        'src="output/facility_emissions.html"'),
        ('"/wind-rose/winter"',     '"output/wind_rose_winter.png"'),
        ('"/wind-rose/spring"',     '"output/wind_rose_spring.png"'),
        ('"/wind-rose/summer"',     '"output/wind_rose_summer.png"'),
        ('"/wind-rose/fall"',       '"output/wind_rose_fall.png"'),
        ('"/wind-rose"',            '"output/wind_rose.png"'),
        ('"/output/',               '"output/'),
    ]
    for old, new in replacements:
        html = html.replace(old, new)
    return html


def build():
    # Clean and create docs directory
    if os.path.exists(DOCS_DIR):
        shutil.rmtree(DOCS_DIR)
    os.makedirs(os.path.join(DOCS_DIR, "output"))
    os.makedirs(os.path.join(DOCS_DIR, "presentation-assets"))

    with app.test_client() as client:
        print("Rendering index.html ...")
        index_html = client.get("/").data.decode("utf-8")

        print("Rendering presentation.html ...")
        presentation_html = client.get("/presentation").data.decode("utf-8")

        print("Rendering study-map.html ...")
        study_map_html = client.get("/study-map").data.decode("utf-8")

    index_html = rewrite_site_html(index_html)
    presentation_html = rewrite_site_html(presentation_html)

    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    with open(os.path.join(DOCS_DIR, "presentation.html"), "w", encoding="utf-8") as f:
        f.write(presentation_html)

    with open(os.path.join(DOCS_DIR, "study-map.html"), "w", encoding="utf-8") as f:
        f.write(study_map_html)

    print("Copying output files ...")
    count = 0
    for fname in os.listdir(OUTPUT_SRC):
        src = os.path.join(OUTPUT_SRC, fname)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(DOCS_DIR, "output", fname))
            print(f"  {fname}")
            count += 1

    print("Copying presentation assets ...")
    asset_count = 0
    if os.path.exists(PRESENTATION_SRC):
        for fname in os.listdir(PRESENTATION_SRC):
            src = os.path.join(PRESENTATION_SRC, fname)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(DOCS_DIR, "presentation-assets", fname))
                print(f"  {fname}")
                asset_count += 1

    open(os.path.join(DOCS_DIR, ".nojekyll"), "w").close()

    print(f"\nDone! Static site built in {DOCS_DIR}/")
    print("  index.html")
    print("  presentation.html")
    print("  study-map.html")
    print(f"  output/ ({count} files)")
    print(f"  presentation-assets/ ({asset_count} files)")
    print(f"\nPreview locally:  python -m http.server 8000 -d {DOCS_DIR}")
    print("Then open:        http://localhost:8000")


if __name__ == "__main__":
    build()
