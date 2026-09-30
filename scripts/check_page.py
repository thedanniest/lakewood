#!/usr/bin/env python3
"""Check the village-road page: one labeled purple road, the rest thin and dark."""

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = (13.6104, 100.7633)
CLUSTER = (13.61523, 100.77697)
NAMED_WAY_ID = 931312194
FOOTER = "ระดับน้ำล่าสุด ไม่ใช่ทางที่รถผ่านได้"
VILLAGE_WAY_IDS = {
    597161191,
    597161192,
    597161193,
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
    597242092,
    597242094,
    597242095,
    597242097,
    597242099,
    597242100,
    694361340,
}
ALLOWED_KEYS = {"osm_way_id", "highway", "access", "link_to_network", "cut_at_village_edge"}
SCALE_LABELS = ["0", "1–10", "11–20", "21–40", "41–70", "71 ขึ้นไป"]


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


def channels(color):
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def is_green(color):
    red, green, blue = channels(color)
    return green > red + 25 and green > blue + 25


def is_purple(color):
    red, green, blue = channels(color)
    return blue > red > green and blue > 120 and green < 90


def is_red(color):
    red, green, blue = channels(color)
    return red > green + 40 and red > blue + 40 and green < 120 and blue < 120


def color_for(cm, scale):
    for step in scale:
        if step["through"] is None or cm <= step["through"]:
            return step["color"]
    raise AssertionError("depth fell off the scale")


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
    if not isinstance(links, list) or len(links) != 1:
        errors.append("soi labels must be the one link for ซอย 11")
        links = []
    for link in links:
        if set(link) != {"osm_way_id", "label", "depth_cm"}:
            errors.append("soi link has unexpected fields")
        if link.get("osm_way_id") != NAMED_WAY_ID or link.get("label") != "ซอย 11":
            errors.append("wrong name on a road")
        depth = link.get("depth_cm")
        if isinstance(depth, bool) or depth != 95.5:
            errors.append("named road depth is not the unrounded 95.5 cm reading")
        label = str(link.get("label", ""))
        if label in {"ซอย 5", "ซอย 7", "ซอย 9"} or re.search(r"\d+\s*-\s*\d+", label):
            errors.append("wrong name on a road")

    features = geo["features"]
    if not 30 <= len(features) <= 40:
        errors.append(f"unexpected road count: {len(features)}")
    way_ids = [feature["properties"].get("osm_way_id") for feature in features]
    if len(way_ids) != len(set(way_ids)):
        errors.append("a road way id is repeated")
    missing = VILLAGE_WAY_IDS - set(way_ids)
    if missing:
        errors.append(f"roads already on the page were dropped: {sorted(missing)}")
    if NAMED_WAY_ID not in way_ids:
        errors.append("named way 931312194 is missing")

    nearest = float("inf")
    distances = []
    for feature in features:
        props = feature["properties"]
        way_id = props.get("osm_way_id")
        if props.get("highway") != "residential" or props.get("access") != "private":
            errors.append(f"way {way_id} is not a private residential road")
        extra = set(props) - ALLOWED_KEYS
        if extra:
            errors.append(f"way {way_id} has unexpected fields {sorted(extra)}")
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
        distances.append((distance, way_id))
        if max(easts) > 2010:
            errors.append(f"way {way_id} is farther than about 2 km east of the club pin")
        if distance > 400 and max(easts) > 840:
            errors.append(f"way {way_id} is outside the village and outside the named cluster")
        if distance > 400 and (max(norths) > 1800 or min(norths) < -200):
            errors.append(f"way {way_id} is outside the golf village")
        if distance <= 400 and (max(norths) > 2500 or min(norths) < -500):
            errors.append(f"way {way_id} leaves the named cluster by too far")
        blob = json.dumps(props)
        if re.search(r"service|track|path|golf", blob, re.I):
            errors.append(f"way {way_id} looks like a service path")
        colored = way_id == NAMED_WAY_ID
        if colored:
            continue
        if "depth_cm" in props or "color" in props or "label" in props:
            errors.append(f"unlabeled way {way_id} is colored")
    distances.sort()
    if not distances or distances[0][1] != NAMED_WAY_ID or distances[0][0] > 2:
        errors.append("ซอย 11 is not the line under 13.61523, 100.77697")
    if len(distances) < 2 or distances[1][0] < 50:
        errors.append("another road is close enough that the soi name would be a guess")
    if nearest > 30:
        errors.append(f"pin is {nearest:.0f} m from the nearest road")

    html = (ROOT / "index.html").read_text(encoding="utf-8")
    if FOOTER not in html:
        errors.append("footer caption is missing")
    if "These are the village roads, not the water level." in html:
        errors.append("old caption is still on the page")
    if "ไม่มีข้อมูล" in html:
        errors.append("legend includes ไม่มีข้อมูล, which would read as the other roads being dry")
    without_footer = html.replace(FOOTER, "")
    if "ผ่านได้" in without_footer:
        errors.append("green or another label says ผ่านได้")
    if "sample-not-a-reading" in html:
        errors.append("the fake sample is drawn on the page")
    if re.search(r"google|maps\.googleapis|AIza|cartocdn|api key", html, re.I):
        errors.append("page mentions Google, CARTO, or an API key")
    if "tile.openstreetmap.org" not in html:
        errors.append("basemap is not OpenStreetMap")
    if "setView(CLUSTER, 17)" not in html or "setView(PIN" in html:
        errors.append("default view is not the named cluster")
    depth_fn = html[html.find("function depthText") : html.find("function readingsByWay")]
    if "Math.round" in depth_fn or "toFixed" in depth_fn or 'return cm.toString() + " ซม."' not in depth_fn:
        errors.append("depth text is rounded")
    for snippet in (
        "if (!SHORT_SOI.test(label)) return;",
        'if (typeof depth !== "number" || !isFinite(depth)) return;',
        "if (!reading)",
        "UNNAMED_COLOR",
        "reading.color",
    ):
        if snippet not in html:
            errors.append("an unlabeled road can take a depth color")
    unnamed_at = html.find("if (!reading)")
    color_at = html.find("reading.color")
    if unnamed_at < 0 or color_at < 0 or unnamed_at > color_at:
        errors.append("an unlabeled road can take a depth color")

    match = re.search(r"var SHORT_SOI = /(\^.*\$)/;", html)
    if not match:
        errors.append("soi label pattern is missing")
    else:
        pattern = match.group(1).replace("\\/", "/")
        soi = re.compile(pattern)
        if not soi.match("ซอย 11") or not soi.match("ซอย 15/2"):
            errors.append("a later label such as ซอย 15/2 cannot display")
        if soi.match("ซอย 45-51") or soi.match("ซอย 15-2") or soi.match("ซอย ตัวอย่าง"):
            errors.append("soi label pattern accepts a range or a wrong name")
        for blocked in ("ซอย 5", "ซอย 7", "ซอย 9"):
            if blocked in html:
                errors.append(f"page labels {blocked}")

    scale_at = html.find("var DEPTH_SCALE = ")
    if scale_at < 0:
        errors.append("depth scale is missing")
        scale = []
    else:
        scale = json.loads(html[scale_at + len("var DEPTH_SCALE = ") : html.find("];", scale_at) + 1])
    if [step.get("label") for step in scale] != SCALE_LABELS:
        errors.append("legend labels are not the depth scale")
    if scale:
        purple = color_for(95.5, scale)
        if purple != scale[-1]["color"] or not is_purple(purple):
            errors.append("95.5 cm is not purple")
        if not is_red(color_for(70, scale)) or is_purple(color_for(70, scale)):
            errors.append("purple is not the top of the scale")
        if color_for(71, scale) != purple:
            errors.append("71 cm is not the purple step")
        if not is_green(color_for(0, scale)) or scale[0]["label"] != "0":
            errors.append("0 cm is not green")
        if not is_green(color_for(10, scale)):
            errors.append("1–10 cm is not light green")
        if "UNNAMED_COLOR" not in html or "#4a453f" not in html:
            errors.append("unnamed roads are not a thin dark stroke")
        if "#4a453f" in {step["color"] for step in scale}:
            errors.append("unnamed roads are drawn as a depth color")

    for text in (
        (ROOT / "data" / "village-roads.geojson").read_text(encoding="utf-8"),
        (ROOT / "data" / "soi-labels.json").read_text(encoding="utf-8"),
        html,
        (ROOT / "README.md").read_text(encoding="utf-8"),
    ):
        if "addr:housenumber" in text or "house_number" in text or "บ้านเลขที่" in text:
            errors.append("a house number is in the repo")

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
        "stay out of github",
        "ซอย 11",
        "95.5",
        "thin dark",
    ):
        if phrase not in readme:
            errors.append(f"README is missing: {phrase}")

    if errors:
        for error in errors:
            print("FAIL", error)
        raise SystemExit(1)
    print(
        f"ok {len(features)} roads, nearest {nearest:.1f} m, "
        f"ซอย 11 at {distances[0][0]:.2f} m, next road {distances[1][0]:.1f} m"
    )


if __name__ == "__main__":
    main()
