import folium
import osmnx
from pyinaturalist import get_observations, pprint
from html import escape
from folium.plugins import MarkerCluster

center = (43.5978, -84.7675)
radius= 10
place_name = "Mount Pleasant, Michigan, USA"


parks = osmnx.features_from_point(
    center,
    tags={
        "leisure": "park",
        },
    dist=radius*1000,
)

rivers = osmnx.features_from_point(
    center,
    tags={
        "waterway": "river"
        },
    dist=radius*1000,
)

observations = get_observations(
    lat=center[0],
    lng=center[1],
    radius=radius*1.2,
    quality_grade="research",
    geo=True,
    per_page=200,
    page=1,
)

# Keep just the fields needed for the map.
parks = parks.reindex(columns=["name", "geometry"]).copy()
#observations = observations.reindex(columns=["name", "geometry"]).copy()

parks["name"] = parks["name"].fillna("Unnamed park")
#observations["name"] = observations["name"].fillna("Unnamed observation")


park_map = folium.Map(location=center, zoom_start=12)

folium.GeoJson(
    #animals.to_json(),
    parks.to_json(),
    tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=[ "Park"]),
    style_function=lambda feature: {
        "color": "#228b22",
        "fillColor": "#65c466",
        "fillOpacity": 0.5,
        "weight": 2,
    },
).add_to(park_map)

animal_layer = MarkerCluster(name="Animal observations").add_to(park_map)

for obs in observations["results"]:
    coordinates = (obs.get("geojson") or {}).get("coordinates")
    if not coordinates:
        continue

    # GeoJSON uses longitude, latitude; Folium uses latitude, longitude.
    lng, lat = coordinates

    taxon = obs.get("taxon") or {}
    name = (
        taxon.get("preferred_common_name")
        or taxon.get("name")
        or "Unknown animal"
    )
    date = str(obs.get("observed_on") or "Unknown date")

    folium.Marker(
        location=[lat, lng],
        tooltip=escape(name),
        popup=folium.Popup(
            f"<b>{escape(name)}</b><br>"
            f"Observed: {escape(date)}<br>"
            f'<a href="https://www.inaturalist.org/observations/{obs["id"]}" '
            f'target="_blank">View observation</a>',
            max_width=300,
        ),
        icon=folium.Icon(color="orange", icon="info-sign"),
    ).add_to(animal_layer)

folium.LayerControl().add_to(park_map)
park_map.save("parks.html")

print(f"Observation {obs['id']}: latitude={lat}, longitude={lng}")

for park_id, park in parks.to_crs(epsg=4326).iterrows():
    if park.geometry is None or park.geometry.is_empty:
        continue

    point = park.geometry.representative_point()

    print(
        f"{park['name']}: "
        f"latitude={point.y}, longitude={point.x}"
    )

    folium.Marker(
        location=[point.y, point.x],
        tooltip=escape(str(park["name"])),
        popup=f"Latitude: {point.y}<br>Longitude: {point.x}",
        icon=folium.Icon(color="green", icon="info-sign"),
    ).add_to(park_map)
