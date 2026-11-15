from datetime import date, datetime, timezone
from pathlib import Path

import json
import math
import hashlib

import osmnx # for mapping parks
from pyinaturalist import ClientSession, get_observations #for mappiung observations

from pyproj import Geod, Transformer
from shapely import get_coordinates, transform
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / 'cache' / 'explorer'
CACHE.mkdir(parents=True, exist_ok=True)

CENTER = (43.5978, -84.7675)
PARK_DISTANCE = 10_000
OBSERVATIONS_PER_PARK = 200
GEOD = Geod(ellps='WGS84')
TO_METERS = Transformer.from_crs(4326, 32616, always_xy=True).transform
TO_WGS84 = Transformer.from_crs(32616, 4326, always_xy=True).transform

def park_center(geometry):
    if not isinstance(geometry, BaseGeometry) or geometry.is_empty:
        raise ValueError('Cannot calculate the center of an empty geometry')
    projected = transform(geometry, TO_METERS, interleaved=False)
    center = transform(projected.centroid, TO_WGS84, interleaved=False)
    return [center.y, center.x]


def find_farthest_point(geometry, center):
    """Return the longest center-to-boundary distance in meters."""
    if not isinstance(geometry, BaseGeometry) or geometry.is_empty:
        raise ValueError('Cannot calculate a radius for an empty geometry')
    projected = transform(geometry, TO_METERS, interleaved=False)
    boundary = projected.boundary if projected.geom_type in ('Polygon', 'MultiPolygon') else projected
    # Include points between vertices so long boundary segments are also checked.
    boundary = transform(boundary.segmentize(20), TO_WGS84, interleaved=False)
    return max((GEOD.inv(center[1], center[0], lng, lat)[2]
                for lng, lat in get_coordinates(boundary)), default=0.0)


def park_circle(geometry):
    center = park_center(geometry)
    return center, find_farthest_point(geometry, center)


# returns true if coordinates are within a circle
def in_circle(center, radius_m, coordinates):
    lng, lat = coordinates
    return GEOD.inv(center[1], center[0], lng, lat)[2] <= radius_m + 0.01


def fetch_parks(refresh=False):
    path = CACHE / 'parks-per-park-v1.json'
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    osmnx.settings.cache_folder = str(ROOT / 'cache')
    osmnx.settings.use_cache = not refresh
    features = osmnx.features_from_point(CENTER, tags={'leisure': 'park'}, dist=PARK_DISTANCE).to_crs(4326)
    parks = []
    for osm_id, row in features.iterrows():
        geometry = row.geometry
        if not isinstance(geometry, BaseGeometry) or geometry.is_empty:
            continue
        if not geometry.is_valid:
            from shapely import make_valid
            geometry = make_valid(geometry)
        if geometry.is_empty:
            continue
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
                      'coverage_complete': True})
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
    observed_on = obs.get('observed_on')
    if isinstance(observed_on, datetime):
        observed_on = observed_on.date()
    if isinstance(observed_on, date):
        observed_on = observed_on.isoformat()
    return {'id': obs['id'], 'coordinates': coords, 'taxon_id': taxon.get('id', 0),
            'name': taxon.get('preferred_common_name') or taxon.get('name') or 'Unidentified organism',
            'scientific_name': taxon.get('name') or '', 'rank': taxon.get('rank') or 'unknown',
            'group': taxon.get('iconic_taxon_name') or 'Other',
            'date': observed_on or 'Date unavailable',
            'observer': user.get('name') or user.get('login') or 'Unknown observer',
            'quality': obs.get('quality_grade') or 'unknown',
            'obscured': bool(obs.get('obscured') or obs.get('geoprivacy') == 'obscured'),
            'photos': photos}


def observation_session():
    session = ClientSession(
        cache_file=CACHE / 'inat-requests.sqlite',
        ratelimit_path=str(CACHE / 'inat-ratelimit.sqlite'),
        lock_path=str(CACHE / 'inat-ratelimit.lock'),
        user_agent='MountPleasantParkExplorer/1.0',
        max_retries=4, backoff_factor=2, timeout=90, burst=1,
    )
    # Our per-park JSON files are the response cache. --refresh bypasses them.
    session.cache.disabled = True
    return session


def fetch_observations(refresh=False, park=None, session=None):
    if park is None:
        raise ValueError('A park is required')
    if not park['boundary_available'] or park['radius_m'] <= 0:
        return {'results': [], 'total_results': 0, 'returned_count': 0, 'truncated': False}
    params = {
        'lat': park['center'][0], 'lng': park['center'][1],
        'radius': park['radius_m'] / 1000,  # iNaturalist expects kilometers.
        'geo': True, 'per_page': OBSERVATIONS_PER_PARK, 'page': 1,
        'order_by': 'observed_on', 'order': 'desc',
    }
    # IDs avoid duplicate/unsafe names; the query hash invalidates changed circles.
    key = json.dumps({'schema': 1, 'park_id': park['id'], 'params': params}, sort_keys=True)
    digest = hashlib.sha256(key.encode()).hexdigest()
    folder = CACHE / 'per-park'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{digest}.json'
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    if session is None:
        with observation_session() as owned_session:
            return fetch_observations(refresh, park, owned_session)

    raw = get_observations(**params, session=session)
    records = []
    for observation in raw['results']:
        compact = compact_observation(observation)
        if compact is not None and in_circle(park['center'], park['radius_m'], compact['coordinates']):
            records.append(compact)
    records = list({o['id']: o for o in records}.values())
    page = {
        'results': records, 'total_results': raw['total_results'],
        'returned_count': len(raw['results']),
        'truncated': raw['total_results'] > len(raw['results']),
        'fetched_at': datetime.now(timezone.utc).isoformat(),
    }
    # An interrupted write must not leave a broken cache entry.
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(page))
    temporary.replace(path)
    return page


def build_dataset(refresh=False):
    parks = fetch_parks(refresh)
    print(f'Loaded {len(parks)} parks', flush=True)
    observations_by_id = {}
    with observation_session() as session:
        for park in parks:
            page = fetch_observations(refresh, park, session)
            park['observations'] = [o['id'] for o in page['results']]
            park['available_observations'] = page['total_results']
            park['observations_truncated'] = page['truncated']
            park['coverage_complete'] = not page['truncated']
            for observation in page['results']:
                observations_by_id[observation['id']] = observation
            print(f"{park['name']}: {len(page['results'])} loaded / {page['total_results']} available", flush=True)
    return {
        'center': CENTER, 
        'parks': parks,
        'observations': list(observations_by_id.values()),
        'total_observations': len(observations_by_id),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'park_distance_km': PARK_DISTANCE / 1000,
        'observation_scope': 'per_park',
        'observations_per_park': OBSERVATIONS_PER_PARK,
    }
