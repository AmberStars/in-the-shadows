# WE USED CHATGPT CODEX sTO GENERATE DOCUMENTATION AND CONNECT OUR FIGMA DESIGN WITH OUR BACKEND DATA

# Mount Pleasant Park Explorer

A Python-generated interactive map following the Figma Nature Exploration layout. The main map shows only parks; select a park, then a taxon, then an observation to view its actual photos, credits, date and observer.

## Run

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python generate_webpage.py
open parks.html
```

The first run fetches up to the newest 200 public observations around each park. Each park query is cached separately; later runs reuse those responses. Cache keys include the OSM ID, center, radius and query settings. HTML is standalone except for the Leaflet library, map tiles and observation photos, which require internet access.

```sh
.venv/bin/python generate_webpage.py --refresh      # Re-fetch data
.venv/bin/python generate_webpage.py --render-only  # Rebuild UI from saved dataset
```

## Data and geometry

- Center: 43.5978, -84.7675 (Mount Pleasant, Michigan).
- Parks: OSM `leisure=park`, fetched in a 10 km bounding box and filtered to park centers within 10 km. No river overlay or regional observation markers.
- Observations: all taxa and all quality grades, up to 200 per park ordered by observation date (newest first). Each request uses that park’s center and radius, converted from meters to kilometers. `pyinaturalist.get_observations()` and a shared `ClientSession` handle requests, rate limiting and retries. `--refresh` bypasses the JSON response cache.
- Park center: centroid calculated in UTM zone 16N, then transformed to latitude/longitude.
- Park radius: maximum WGS84 geodesic distance from that center to the boundary, including every component of a multipolygon. Boundary segments are sampled at intervals of at most 20 m.
- Membership: public observation point falls within the park's circle, **not** necessarily its polygon. An observation may belong to multiple overlapping park circles. Obscured coordinates remain obscured and are labeled.
- Parks without mapped polygon boundaries remain selectable but have no inferred search radius. Parks with more than 200 available observations are labeled as limited to the newest 200.
- Each taxon card's photo comes from a matching observation. Selecting a record changes to that record's photos; no stock photos or taxon default photos. Missing images have explicit placeholders. Credits, licenses and original observation links are retained.
- `cache/explorer/dataset.json` stores the assembled snapshot. The app contains observations from the individual park queries. Each park stores its own observation IDs, and the combined observation list is deduplicated by ID. The summary reports unique loaded observations, not all observations in the region.

## Files

- `generate_webpage.py`: command-line entry point and HTML generation.
- `park_data.py`: source queries, caching and spatial matching.
- `web/index.html`, `web/styles.css`, `web/app.js`: layout and interactive map.
- `tests/test_per_park.py`: query units, caching, dates, geometry and dataset tests.
- `generate_webpage.original.py`: preserved original script.

Python performs all data fetching and spatial work. The generated browser interface uses Leaflet and a small JavaScript layer for instant park/taxon filtering. No Node build or Python web server is required.

Design reference: https://www.figma.com/proto/tjBH32EmnRTqXdtPhmdlbu/park-map?node-id=0-1
Data: OpenStreetMap contributors (ODbL), iNaturalist contributors and individual photo rights holders. Map tiles: OpenStreetMap. Photos remain hosted by iNaturalist; attribution appears beside each selected photo.
