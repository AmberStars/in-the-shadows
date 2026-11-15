"""Fetch public source data and associate sightings with park-centred circles."""
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / 'cache' / 'explorer'
CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(CACHE / 'matplotlib'))

import numpy as np
import osmnx as ox
import requests
from pyproj import Geod, Transformer
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from shapely import get_coordinates, transform
from shapely.geometry import mapping

CENTER = (43.5978, -84.7675)
PARK_DISTANCE = 10_000
OBS_RADIUS = 12
GEOD = Geod(ellps='WGS84')
TO_METERS = Transformer.from_crs(4326, 32616, always_xy=True).transform
TO_WGS84 = Transformer.from_crs(32616, 4326, always_xy=True).transform


def park_circle(geometry):
    """Metric centroid, then maximum geodesic distance to the park boundary."""
    projected = transform(geometry, TO_METERS, interleaved=False)
    center = transform(projected.centroid, TO_WGS84, interleaved=False)
    # Densify long segments so the entire boundary is represented, including islands.
    boundary = projected.boundary if projected.geom_type in ('Polygon', 'MultiPolygon') else projected
    coords = get_coordinates(transform(boundary.segmentize(20), TO_WGS84, interleaved=False))
    if not len(coords):
        coords = np.array([[center.x, center.y]])
    _, _, distances = GEOD.inv(np.full(len(coords), center.x), np.full(len(coords), center.y), coords[:, 0], coords[:, 1])
    return [center.y, center.x], float(max(distances))


def in_circle(center, radius_m, coordinates):
    lng, lat = coordinates
    return GEOD.inv(center[1], center[0], lng, lat)[2] <= radius_m + 0.01


def fetch_parks(refresh=False):
    path = CACHE / 'parks.json'
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    ox.settings.cache_folder = str(ROOT / 'cache')
    ox.settings.use_cache = not refresh
    features = ox.features_from_point(CENTER, tags={'leisure': 'park'}, dist=PARK_DISTANCE).to_crs(4326)
    parks = []
    for osm_id, row in features.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.is_empty:
            continue
        if not geometry.is_valid:
            from shapely import make_valid
            geometry = make_valid(geometry)
        center, radius = park_circle(geometry)
        # OSMnx queries a box; retain parks whose centers are within the requested 10 km.
        if not in_circle(CENTER, PARK_DISTANCE, [center[1], center[0]]):
            continue
        name = row.get('name')
        if not isinstance(name, str) or not name.strip():
            name = 'Unnamed park'
        parks.append({'id': '/'.join(map(str, osm_id)), 'name': name,
                      'center': center, 'radius_m': radius, 'geometry': mapping(geometry),
                      'boundary_available': geometry.geom_type in ('Polygon', 'MultiPolygon'),
                      'coverage_complete': GEOD.inv(CENTER[1], CENTER[0], center[1], center[0])[2] + radius <= OBS_RADIUS * 1000})
    parks.sort(key=lambda p: p['name'])
    path.write_text(json.dumps(parks))
    return parks


def compact_observation(obs):
    taxon = obs.get('taxon') or {}
    coords = (obs.get('geojson') or {}).get('coordinates')
    if not coords or len(coords) != 2 or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in coords):
        return None
    photos = []
    for p in obs.get('photos') or []:
        url = p.get('url') or ''
        if p.get('hidden') or not url.startswith('https://'):
            continue
        photos.append({'url': url.replace('/square.', '/medium.'), 'credit': p.get('attribution') or '', 'license': p.get('license_code') or 'All rights reserved'})
    user = obs.get('user') or {}
    return {'id': obs['id'], 'coordinates': coords, 'taxon_id': taxon.get('id', 0),
            'name': taxon.get('preferred_common_name') or taxon.get('name') or 'Unidentified organism',
            'scientific_name': taxon.get('name') or '', 'rank': taxon.get('rank') or 'unknown',
            'group': taxon.get('iconic_taxon_name') or 'Other',
            'date': obs.get('observed_on') or 'Date unavailable',
            'observer': user.get('name') or user.get('login') or 'Unknown observer',
            'quality': obs.get('quality_grade') or 'unknown',
            'obscured': bool(obs.get('obscured') or obs.get('geoprivacy') == 'obscured'),
            'photos': photos}


def fetch_observations(refresh=False):
    session = requests.Session()
    session.headers['User-Agent'] = 'MountPleasantParkExplorer/1.0'
    session.mount('https://', HTTPAdapter(max_retries=Retry(total=4, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])))
    observations, cursor, total = [], 0, None
    while True:
        path = CACHE / f'observations-{cursor}.json'
        if path.exists() and not refresh:
            page = json.loads(path.read_text())
        else:
            response = session.get('https://api.inaturalist.org/v1/observations', params={
                'lat': CENTER[0], 'lng': CENTER[1], 'radius': OBS_RADIUS, 'geo': 'true',
                'per_page': 200, 'order_by': 'id', 'order': 'asc', 'id_above': cursor,
            }, timeout=(15, 90))
            response.raise_for_status()
            raw = response.json()
            records = raw['results']
            page = {'total': raw['total_results'], 'next': max((o['id'] for o in records), default=cursor),
                    'count': len(records), 'results': [o for o in map(compact_observation, records) if o]}
            path.write_text(json.dumps(page))
            time.sleep(1.05)
        if total is None:
            total = page['total']
        observations.extend(page['results'])
        print(f'Observations: {len(observations):,} / approximately {total:,}', flush=True)
        if page['count'] < 200:
            break
        if page['next'] <= cursor:
            raise RuntimeError('Observation pagination did not advance; refusing incomplete output.')
        cursor = page['next']
    return list({o['id']: o for o in observations}.values())


def build_dataset(refresh=False):
    parks = fetch_parks(refresh)
    print(f'Loaded {len(parks)} parks', flush=True)
    observations = fetch_observations(refresh)
    coords = np.array([o['coordinates'] for o in observations])
    for park in parks:
        if not len(coords) or not park['boundary_available']:
            park['observations'] = []
            continue
        _, _, distances = GEOD.inv(np.full(len(coords), park['center'][1]), np.full(len(coords), park['center'][0]), coords[:, 0], coords[:, 1])
        park['observations'] = [o['id'] for o, d in zip(observations, distances) if d <= park['radius_m'] + 0.01]
    matched = {oid for p in parks for oid in p['observations']}
    return {'center': CENTER, 'parks': parks, 'observations': [o for o in observations if o['id'] in matched],
            'total_observations': len(observations), 'generated_at': datetime.now(timezone.utc).isoformat(),
            'park_distance_km': 10, 'observation_distance_km': 12}
