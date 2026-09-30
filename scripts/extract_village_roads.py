#!/usr/bin/env python3
"""Save Lakewood village residential roads from OpenStreetMap.

The country-club pin is 13.6104, 100.7633. The streets are
highway=residential and access=private. Service paths, tracks, and
golf-cart lines are not downloaded.

Roads already published west of the fairway edge stay as they are.
Private residential roads in the same connected network are added when
they come within 400 m of the named cluster at 13.61523, 100.77697.
Nothing farther than 2 km east of the pin is kept, so the next estate
stays out.
"""

import json
import math
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

PIN = (13.6104, 100.7633)
# The Google label "Soi Mu Ban Lake Wood 11" is printed here.
CLUSTER = (13.61523, 100.77697)
CLUSTER_RADIUS_M = 400.0
# East of this line is the next estate, not this village.
EAST_CAP_M = 2000.0
NAMED_WAY_ID = 931312194
# south, west, north, east. Wide enough that the private network is not cut.
BBOX = (13.605, 100.755, 13.650, 100.810)
GAP_M = 12.0
OVERPASS_URLS = (
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass-api.de/api/interpreter",
)
ROOT = Path(__file__).resolve().parents[1]


def hav(a, b):
    radius = 6371000.0
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlat = math.radians(b[0] - a[0])
    dlon = math.radians(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def fetch_ways():
    south, west, north, east = BBOX
    query = f"""
[out:json][timeout:90];
way["highway"="residential"]["access"="private"]({south},{west},{north},{east});
out tags geom;
"""
    data = urllib.parse.urlencode({"data": query}).encode()
    payload = None
    last_error = None
    for url in OVERPASS_URLS:
        req = urllib.request.Request(
            url,
            data=data,
            headers={"User-Agent": "LakewoodVillageRoads/1.0 (static geometry extract)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.load(resp)
            break
        except Exception as error:
            last_error = error
    if payload is None:
        raise SystemExit(f"Overpass request failed: {last_error}")
    ways = []
    for element in payload.get("elements", []):
        geom = element.get("geometry") or []
        if element.get("type") != "way" or len(geom) < 2:
            continue
        tags = element.get("tags") or {}
        if tags.get("highway") != "residential" or tags.get("access") != "private":
            continue
        ways.append({"id": element["id"], "tags": tags, "geometry": geom})
    timestamp = (payload.get("osm3s") or {}).get("timestamp_osm_base")
    return ways, timestamp


def node_key(point):
    return (round(point["lat"], 6), round(point["lon"], 6))


def build_adjacency(ways):
    at_node = defaultdict(set)
    for way in ways:
        for point in way["geometry"]:
            at_node[node_key(point)].add(way["id"])
    adjacent = defaultdict(set)
    for ids in at_node.values():
        ids = list(ids)
        for i, left in enumerate(ids):
            for right in ids[i + 1 :]:
                adjacent[left].add(right)
                adjacent[right].add(left)
    return adjacent


def component_from(seed, adjacent):
    seen = {seed}
    stack = [seed]
    while stack:
        current = stack.pop()
        for other in adjacent[current]:
            if other not in seen:
                seen.add(other)
                stack.append(other)
    return seen


def min_distance(geom, points):
    best = float("inf")
    for point in geom:
        for lat, lon in points:
            if abs(point["lat"] - lat) > 0.0004:
                continue
            best = min(best, hav((point["lat"], point["lon"]), (lat, lon)))
            if best <= GAP_M:
                return best
    return best


def select(ways):
    by_id = {way["id"]: way for way in ways}
    adjacent = build_adjacency(ways)
    seed = min(
        ways,
        key=lambda way: min(hav(PIN, (p["lat"], p["lon"])) for p in way["geometry"]),
    )
    selected = component_from(seed["id"], adjacent)
    joined_by_gap = set()
    grew = True
    while grew:
        grew = False
        cloud = [
            (point["lat"], point["lon"])
            for way_id in selected
            for point in by_id[way_id]["geometry"]
        ]
        for way in ways:
            if way["id"] in selected:
                continue
            if min_distance(way["geometry"], cloud) > GAP_M:
                continue
            extra = component_from(way["id"], adjacent)
            joined_by_gap |= extra - selected
            selected |= extra
            grew = True
            break
    return selected, joined_by_gap, seed["id"]


def line_distance_to_pin(geom):
    return min(hav(PIN, (point["lat"], point["lon"])) for point in geom)


def east_metres(lon):
    return (lon - PIN[1]) * 111320.0 * math.cos(math.radians(PIN[0]))


def north_metres(lat):
    return (lat - PIN[0]) * 111320.0


def lonlat_from_metres(east, north):
    lon = PIN[1] + east / (111320.0 * math.cos(math.radians(PIN[0])))
    lat = PIN[0] + north / 111320.0
    return [round(lon, 6), round(lat, 6)]


def to_metres(lat, lon):
    return east_metres(lon), north_metres(lat)


def point_segment_distance(point, start, end):
    px, py = point
    ax, ay = start
    bx, by = end
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - ax, py - ay)
    ratio = ((px - ax) * dx + (py - ay) * dy) / length_sq
    ratio = max(0.0, min(1.0, ratio))
    return math.hypot(px - (ax + ratio * dx), py - (ay + ratio * dy))


def line_distance_to(coordinates, lat, lon):
    origin = to_metres(lat, lon)
    metres = [to_metres(lat_i, lon_i) for lon_i, lat_i in coordinates]
    best = float("inf")
    for start, end in zip(metres, metres[1:]):
        best = min(best, point_segment_distance(origin, start, end))
    return best


def clip_to_max_east(coordinates, max_east):
    """Drop the part of a [lon, lat] line that has entered the next estate."""
    measured = [(east_metres(lon), north_metres(lat)) for lon, lat in coordinates]
    if all(east <= max_east for east, _north in measured):
        return [coordinates]
    pieces = []
    current = []

    def emit():
        nonlocal current
        if len(current) >= 2:
            pieces.append(current)
        current = []

    for index, (east, north) in enumerate(measured):
        if east <= max_east:
            if not current and index > 0 and measured[index - 1][0] > max_east:
                previous_east, previous_north = measured[index - 1]
                span = east - previous_east
                ratio = (max_east - previous_east) / span
                current.append((max_east, previous_north + (north - previous_north) * ratio))
            current.append((east, north))
            continue
        if current:
            previous_east, previous_north = current[-1]
            span = east - previous_east
            ratio = (max_east - previous_east) / span
            current.append((max_east, previous_north + (north - previous_north) * ratio))
            emit()
    emit()
    lines = []
    for piece in pieces:
        length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(piece, piece[1:]))
        if length < 20:
            continue
        lines.append([lonlat_from_metres(east, north) for east, north in piece])
    return lines


def as_feature(way, joined_by_gap):
    coordinates = [
        [round(point["lon"], 6), round(point["lat"], 6)] for point in way["geometry"]
    ]
    return {
        "type": "Feature",
        "properties": {
            "osm_way_id": way["id"],
            "highway": "residential",
            "access": "private",
            "link_to_network": "within_12m" if way["id"] in joined_by_gap else "shared_node",
        },
        "geometry": {"type": "LineString", "coordinates": coordinates},
    }


def published_features():
    path = ROOT / "data" / "village-roads.geojson"
    return json.loads(path.read_text(encoding="utf-8"))["features"]


def cluster_features(ways, selected, joined_by_gap):
    by_id = {way["id"]: way for way in ways}
    features = []
    distances = []
    for way_id in sorted(selected):
        way = by_id[way_id]
        coordinates = [
            [round(point["lon"], 6), round(point["lat"], 6)] for point in way["geometry"]
        ]
        distance = line_distance_to(coordinates, CLUSTER[0], CLUSTER[1])
        distances.append((distance, way_id))
        if distance > CLUSTER_RADIUS_M:
            continue
        for line in clip_to_max_east(coordinates, EAST_CAP_M):
            if line_distance_to(line, CLUSTER[0], CLUSTER[1]) > CLUSTER_RADIUS_M:
                continue
            feature = as_feature(way, joined_by_gap)
            feature["geometry"]["coordinates"] = line
            features.append(feature)
    distances.sort()
    return features, distances


def main():
    published = published_features()
    ways, timestamp = fetch_ways()
    selected, joined_by_gap, seed = select(ways)
    added, distances = cluster_features(ways, selected, joined_by_gap)
    if not distances or distances[0][1] != NAMED_WAY_ID or distances[0][0] > 2:
        raise SystemExit(f"named way {NAMED_WAY_ID} is not the line under the soi point: {distances[:3]}")
    if len(distances) < 2 or distances[1][0] < 50:
        raise SystemExit(f"another private road is too close to the soi point: {distances[:3]}")
    added_ids = {feature["properties"]["osm_way_id"] for feature in added}
    if NAMED_WAY_ID not in added_ids:
        raise SystemExit(f"named way {NAMED_WAY_ID} was not added")
    # Roads already on the page stay, except a published clip of a way that
    # itself reaches the named cluster. That way is drawn once, in full,
    # from the cluster extract above.
    kept = [
        feature
        for feature in published
        if feature["properties"]["osm_way_id"] not in added_ids
    ]
    features = kept + added
    nearest = min(
        line_distance_to_pin(
            [{"lon": lon, "lat": lat} for lon, lat in feature["geometry"]["coordinates"]]
        )
        for feature in features
    )
    if nearest > 30:
        raise SystemExit(f"club pin is {nearest:.0f} m from the nearest kept road")
    collection = {"type": "FeatureCollection", "features": features}
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    geojson_path = data_dir / "village-roads.geojson"
    geojson_path.write_text(json.dumps(collection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    js = (
        "/* Village residential roads. OSM data © OpenStreetMap contributors, ODbL. */\n"
        f"/* osm_timestamp: {timestamp} */\n"
        "window.LAKEWOOD_ROADS = "
        + json.dumps(collection, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    (data_dir / "village-roads.js").write_text(js, encoding="utf-8")
    meta = {
        "pin": [PIN[0], PIN[1]],
        "named_cluster": [CLUSTER[0], CLUSTER[1]],
        "osm_timestamp": timestamp,
        "feature_count": len(features),
        "kept_published_count": len(kept),
        "cluster_count": len(added),
        "joined_within_12m": sorted(
            way_id
            for way_id in joined_by_gap
            if any(feature["properties"]["osm_way_id"] == way_id for feature in features)
        ),
        "seed_osm_way_id": seed,
        "nearest_road_metres": round(nearest, 1),
        "named_way_osm_id": NAMED_WAY_ID,
        "named_way_distance_m": round(distances[0][0], 2),
        "next_way_distance_m": round(distances[1][0], 1),
        "cluster_radius_metres": CLUSTER_RADIUS_M,
        "east_cap_metres": EAST_CAP_M,
        "filter": (
            "highway=residential and access=private, connected through the club pin. "
            "Roads already on the page stay. Other roads in that network are added "
            "when they come within 400 m of 13.61523, 100.77697. "
            "Nothing farther than 2 km east of the pin is included. "
            "Service paths, tracks, and golf-cart lines are not included."
        ),
    }
    (data_dir / "village-roads.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {len(features)} roads, seed {seed}, "
        f"nearest {nearest:.1f} m, osm {timestamp}"
    )


if __name__ == "__main__":
    main()
