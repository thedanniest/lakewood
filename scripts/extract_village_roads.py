#!/usr/bin/env python3
"""Save Lakewood village residential roads from OpenStreetMap.

The country-club pin is 13.6104, 100.7633. The village streets through
that pin are highway=residential and access=private. Service paths,
tracks, and golf-cart lines are not downloaded.

A few private residential ways at the north edge are drawn a few metres
short of a shared node (a roundabout and the streets on it). Ways within
12 metres of the network are kept. Private ways farther off stay out.
"""

import json
import math
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

PIN = (13.6104, 100.7633)
# south, west, north, east. Wide enough that the private network is not cut.
BBOX = (13.605, 100.755, 13.650, 100.810)
GAP_M = 12.0
OVERPASS = "https://overpass.openstreetmap.fr/api/interpreter"
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
    req = urllib.request.Request(
        OVERPASS,
        data=data,
        headers={"User-Agent": "LakewoodVillageRoads/1.0 (static geometry extract)"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.load(resp)
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


def main():
    ways, timestamp = fetch_ways()
    selected, joined_by_gap, seed = select(ways)
    by_id = {way["id"]: way for way in ways}
    features = [as_feature(by_id[way_id], joined_by_gap) for way_id in sorted(selected)]
    nearest = min(line_distance_to_pin(by_id[way_id]["geometry"]) for way_id in selected)
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
        "osm_timestamp": timestamp,
        "feature_count": len(features),
        "joined_within_12m": sorted(joined_by_gap),
        "seed_osm_way_id": seed,
        "nearest_road_metres": round(nearest, 1),
        "filter": (
            "highway=residential and access=private, connected through the club pin. "
            "Private residential ways within 12 m are included. "
            "Service paths, tracks, and other highway types are not."
        ),
    }
    (data_dir / "village-roads.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {len(features)} roads, seed {seed}, "
        f"nearest {nearest:.1f} m, gap-joined {sorted(joined_by_gap)}, osm {timestamp}"
    )


if __name__ == "__main__":
    main()
