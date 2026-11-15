# Mount Pleasant Park Explorer

A Python-generated interactive map following the Figma Nature Exploration layout. The main map shows only parks; select a park, then a taxon, then an observation to view its actual photos, credits, date and observer.

## Run

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python OSMx.py
open parks.html
```

The first run fetches approximately 20,000 public observations and can take several minutes. It caches each batch and resumes after interrupted downloads. Later runs reuse cached data. HTML is standalone except for the Leaflet library, map tiles and observation photos, which require internet access.

```sh
.venv/bin/python OSMx.py --refresh      # Re-fetch data
.venv/bin/python OSMx.py --render-only  # Rebuild UI from saved dataset
.venv/bin/python -m unittest discover -s tests -v
```

## Data and geometry

- Center: 43.5978, -84.7675 (Mount Pleasant, Michigan).
- Parks: OSM `leisure=park`, fetched in a 10 km bounding box and filtered to park centers within 10 km. No river overlay or regional observation markers.
- Observations: all taxa and all quality grades, public georeferenced iNaturalist records within 12 km. Cursor pagination avoids the API's 10,000-result page limit. Requests are paced and transient failures retried.
- Park center: centroid calculated in UTM zone 16N, then transformed to latitude/longitude.
- Park radius: maximum WGS84 geodesic distance from that center to the boundary, including every component of a multipolygon. Boundary segments are sampled at intervals of at most 20 m.
- Membership: public observation point falls within the park's circle, **not** necessarily its polygon. An observation may belong to multiple overlapping park circles. Obscured coordinates remain obscured and are labeled.
- Parks without mapped polygon boundaries remain selectable but have no inferred search radius. Park circles extending beyond the regional observation dataset are marked as partially covered.
- Each taxon card's photo comes from a matching observation. Selecting a record changes to that record's photos; no stock photos or taxon default photos. Missing images have explicit placeholders. Credits, licenses and original observation links are retained.
- `cache/explorer/dataset.json` stores the assembled snapshot. The app contains only observations associated with at least one park; the summary reports the full regional fetch.

## Files

- `OSMx.py`: command-line entry point and HTML generation.
- `park_data.py`: source queries, caching and spatial matching.
- `web/index.html`, `web/styles.css`, `web/app.js`: layout and interactive map.
- `tests/test_geometry.py`: radius and membership tests.
- `OSMx.original.py`: preserved original script.

Python performs all data fetching and spatial work. The generated browser interface uses Leaflet and a small JavaScript layer for instant park/taxon filtering. No Node build or Python web server is required.

Design reference: https://www.figma.com/proto/tjBH32EmnRTqXdtPhmdlbu/park-map?node-id=0-1
Data: OpenStreetMap contributors (ODbL), iNaturalist contributors and individual photo rights holders. Map tiles: OpenStreetMap. Photos remain hosted by iNaturalist; attribution appears beside each selected photo.
