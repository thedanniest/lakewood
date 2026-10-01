#!/usr/bin/env python3
"""Check the village-road page stays unlabeled, with one dark road color."""

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = (13.6104, 100.7633)
CLUSTER = (13.61523, 100.77697)
FOOTER = "These are the village roads, not the water level."
WAY_IDS = {
    597161191,
    597161192,
    597161193,
    597241724,
    597241727,
    597241739,
    597241744,
    597241749,
    597241753,
    597241757,
    597241775,
    597242044,
    597242045,
    597242046,
    597242047,
    597242050,
    597242051,
    597242052,
    597242053,
    597242054,
    597242055,
    597242091,
    597242092,
    597242094,
    597242095,
    597242097,
    597242099,
    597242100,
    694361340,
    694361342,
    931312194,
    931312195,
}
ALLOWED_KEYS = {"osm_way_id", "highway", "access", "link_to_network", "cut_at_village_edge"}
ALLOWED_COLORS = {
    "#2c3136",
    "#e7e2d8",
    "#f6f3ee",
    "#d5cfc4",
    "#4a453f",
    "#f7f4ee",
}


def hav(a, b):
    radius = 6371000.0
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlat = math.radians(b[0] - a[0])
    dlon = math.radians(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def to_metres(lat, lon):
    east = (lon - PIN[1]) * 111320.0 * math.cos(math.radians(PIN[0]))
    north = (lat - PIN[0]) * 111320.0
    return east, north


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


def line_distance(coordinates, lat, lon):
    origin = to_metres(lat, lon)
    metres = [to_metres(lat_i, lon_i) for lon_i, lat_i in coordinates]
    best = float("inf")
    for start, end in zip(metres, metres[1:]):
        best = min(best, point_segment_distance(origin, start, end))
    return best


def load_js_assign(path, name):
    text = path.read_text(encoding="utf-8")
    marker = f"window.{name} = "
    start = text.index(marker) + len(marker)
    body = text[start:].strip()
    if body.endswith(";"):
        body = body[:-1]
    return json.loads(body)


def main():
    errors = []
    geo = json.loads((ROOT / "data" / "village-roads.geojson").read_text(encoding="utf-8"))
    js = load_js_assign(ROOT / "data" / "village-roads.js", "LAKEWOOD_ROADS")
    if geo != js:
        errors.append("village-roads.js does not match village-roads.geojson")

    labels = json.loads((ROOT / "data" / "soi-labels.json").read_text(encoding="utf-8"))
    labels_js = load_js_assign(ROOT / "data" / "soi-labels.js", "LAKEWOOD_SOI_LABELS")
    if labels != labels_js:
        errors.append("soi-labels.js does not match soi-labels.json")
    links = labels.get("links")
    if links != []:
        errors.append("a road is labeled")

    features = geo["features"]
    way_ids = [feature["properties"].get("osm_way_id") for feature in features]
    if set(way_ids) != WAY_IDS or len(way_ids) != len(WAY_IDS):
        errors.append(f"road list changed: {len(way_ids)} ways")
    if 931312194 not in way_ids:
        errors.append("way 931312194 was dropped")

    nearest = float("inf")
    for feature in features:
        props = feature["properties"]
        way_id = props.get("osm_way_id")
        if props.get("highway") != "residential" or props.get("access") != "private":
            errors.append(f"way {way_id} is not a private residential road")
        extra = set(props) - ALLOWED_KEYS
        if extra:
            errors.append(f"way {way_id} has unexpected fields {sorted(extra)}")
        if "label" in props or "color" in props or "depth_cm" in props:
            errors.append(f"way {way_id} is labeled or colored")
        if feature["geometry"]["type"] != "LineString":
            errors.append("geometry is not a LineString")
        coordinates = feature["geometry"]["coordinates"]
        easts = []
        norths = []
        for lon, lat in coordinates:
            east, north = to_metres(lat, lon)
            easts.append(east)
            norths.append(north)
            nearest = min(nearest, hav(PIN, (lat, lon)))
        distance = line_distance(coordinates, CLUSTER[0], CLUSTER[1])
        if max(easts) > 2010:
            errors.append(f"way {way_id} is farther than about 2 km east of the club pin")
        if distance > 400 and max(easts) > 840:
            errors.append(f"way {way_id} is outside the village and outside the named cluster")
        if distance > 400 and (max(norths) > 1800 or min(norths) < -200):
            errors.append(f"way {way_id} is outside the golf village")
        blob = json.dumps(props)
        if re.search(r"service|track|path|golf", blob, re.I):
            errors.append(f"way {way_id} looks like a service path")
    if nearest > 30:
        errors.append(f"pin is {nearest:.0f} m from the nearest road")

    html = (ROOT / "index.html").read_text(encoding="utf-8")
    if FOOTER not in html:
        errors.append("disclaimer line is missing")
    if "ระดับน้ำล่าสุด" in html or "ไม่มีข้อมูล" in html or "ผ่านได้" in html:
        errors.append("a depth caption or legend is still on the page")
    if "sample-not-a-reading" in html:
        errors.append("the fake sample is drawn on the page")
    if re.search(r"google|maps\.googleapis|AIza|cartocdn|api key", html, re.I):
        errors.append("page mentions Google, CARTO, or an API key")
    if "tile.openstreetmap.org" not in html:
        errors.append("basemap is not OpenStreetMap")
    if "setView(CLUSTER, 17)" not in html or "setView(PIN" in html:
        errors.append("default view is not the street cluster")
    if "ROAD_COLOR" not in html or "color: halo ? ROAD_HALO : ROAD_COLOR" not in html:
        errors.append("roads are not styled with the single road color")
    if "reading.color" in html or "DEPTH_SCALE" in html or "legend" in html:
        errors.append("a road can take a second color")
    colors = {color.lower() for color in re.findall(r"#[0-9a-fA-F]{6}", html)}
    extra_colors = colors - ALLOWED_COLORS
    if extra_colors:
        errors.append(f"a road uses a second color: {sorted(extra_colors)}")
    for color in colors:
        red = int(color[1:3], 16)
        green = int(color[3:5], 16)
        blue = int(color[5:7], 16)
        if green > red + 25 and green > blue + 25:
            errors.append(f"page uses a green color {color}")
    if re.search(r"ซอย|95\.5|ซม", html):
        errors.append("a road is labeled")

    for text in (
        (ROOT / "data" / "village-roads.geojson").read_text(encoding="utf-8"),
        (ROOT / "data" / "soi-labels.json").read_text(encoding="utf-8"),
        html,
        (ROOT / "README.md").read_text(encoding="utf-8"),
    ):
        if "addr:housenumber" in text or "house_number" in text or "บ้านเลขที่" in text:
            errors.append("a house number is in the repo")
    if "ซอย 24" in (ROOT / "data" / "soi-labels.json").read_text(encoding="utf-8"):
        errors.append("ซอย 24 was added")
    if "ซอย 24" in html:
        errors.append("ซอย 24 was added")

    sample = json.loads((ROOT / "data" / "sample-not-a-reading.json").read_text(encoding="utf-8"))
    sample_text = json.dumps(sample, ensure_ascii=False)
    if sample.get("fake") is not True:
        errors.append("sample is not marked fake")
    if re.search(r"\d", sample_text):
        errors.append("sample contains a digit and could be read as a measurement")
    if "not a water depth" not in sample_text or "not a real house" not in sample_text:
        errors.append("sample does not say it is fake in plain language")

    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    for phrase in (
        "unlabeled",
        "not a live flood",
        "not the water level",
        "stay out of github",
        "thin dark",
    ):
        if phrase not in readme:
            errors.append(f"README is missing: {phrase}")

    if errors:
        for error in errors:
            print("FAIL", error)
        raise SystemExit(1)
    print(f"ok {len(features)} roads, nearest {nearest:.1f} m, labels empty, one road color")


if __name__ == "__main__":
    main()
