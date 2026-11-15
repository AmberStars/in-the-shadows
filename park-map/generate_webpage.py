"""WRITTEN BY CHATGPT CODEX"""
"""Run with .venv/bin/python generate_webpage.py; open parks.html when complete."""
import argparse
import base64
import json
from pathlib import Path
from park_data import build_dataset

#store the root path for the project
ROOT = Path(__file__).resolve().parent


def render(data):
    template = (ROOT / 'web' / 'index.html').read_text()
    # Escape script terminators in third-party text before embedding JSON in HTML.
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    html = template.replace('/* APP_STYLES */', (ROOT / 'web' / 'styles.css').read_text())
    html = html.replace('/* APP_SCRIPT */', (ROOT / 'web' / 'app.js').read_text())
    marker = base64.b64encode((ROOT / 'web' / 'assets' / 'park-marker.svg').read_bytes()).decode()
    html = html.replace('PARK_MARKER_ASSET', 'data:image/svg+xml;base64,' + marker)
    html = html.replace('/* APP_DATA */', payload)
    (ROOT / 'parks.html').write_text(html)
    print(f"Saved {ROOT / 'parks.html'} ({len(data['parks'])} parks, {data['total_observations']:,} observations searched)")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='Refresh source data from both APIs')
    parser.add_argument('--render-only', action='store_true', help='Rebuild the page using the last dataset')
    args = parser.parse_args()
    dataset = ROOT / 'cache' / 'explorer' / 'dataset.json'
    if args.render_only:
        data = json.loads(dataset.read_text())
    else:
        data = build_dataset(args.refresh)
        dataset.write_text(json.dumps(data))
    render(data)
