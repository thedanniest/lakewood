#!/usr/bin/env python3
"""Check the village-road page stays a map of unlabeled residential lines."""

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = (13.6104, 100.7633)


def hav(a, b):
    radius = 6371000.0
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlat = math.radians(b[0] - a[0])
    dlon = math.radians(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


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
    if labels.get("links") != []:
        errors.append("soi label links are not empty")

    features = geo["features"]
    if len(features) < 40:
        errors.append(f"too few roads: {len(features)}")
    nearest = float("inf")
    for feature in features:
        props = feature["properties"]
        if props.get("highway") != "residential" or props.get("access") != "private":
            errors.append(f"way {props.get('osm_way_id')} is not a private residential road")
        if feature["geometry"]["type"] != "LineString":
            errors.append("geometry is not a LineString")
        for lon, lat in feature["geometry"]["coordinates"]:
            if hav(PIN, (lat, lon)) > 5000:
                errors.append(f"way {props.get('osm_way_id')} is more than 5 km from the pin")
                break
            nearest = min(nearest, hav(PIN, (lat, lon)))
        blob = json.dumps(props)
        if re.search(r"service|track|path|golf", blob, re.I):
            errors.append(f"way {props.get('osm_way_id')} looks like a service path")
    if nearest > 30:
        errors.append(f"pin is {nearest:.0f} m from the nearest road")

    html = (ROOT / "index.html").read_text(encoding="utf-8")
    if "These are the village roads, not the water level." not in html:
        errors.append("disclaimer line is missing")
    if "sample-not-a-reading" in html:
        errors.append("the fake sample is drawn on the page")
    if re.search(r"google|maps\.googleapis|AIza", html, re.I):
        errors.append("page mentions Google or an API key")
    colors = set(re.findall(r"#[0-9a-fA-F]{6}", html))
    for color in colors:
        red = int(color[1:3], 16)
        green = int(color[3:5], 16)
        blue = int(color[5:7], 16)
        if green > red + 25 and green > blue + 25:
            errors.append(f"page uses a green color {color}")
    if html.count("ROAD_COLOR") < 1 or html.count('color: ROAD_COLOR') < 1:
        errors.append("roads are not styled with the single road color")

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
    ):
        if phrase not in readme:
            errors.append(f"README is missing: {phrase}")

    if errors:
        for error in errors:
            print("FAIL", error)
        raise SystemExit(1)
    print(f"ok {len(features)} roads, nearest {nearest:.1f} m, labels empty, disclaimer present")


if __name__ == "__main__":
    main()
