# Lakewood village roads

One page of the residential roads in Lakewood village, at Lakewood Country Club near Wat Srirattanatharam in Bang Phli, Samut Prakan. The map opens on the streets around 13.61523, 100.77697, about a kilometre east of the club pin at 13.6104, 100.7633.

Every road is unlabeled. Each one is a thin dark stroke. OSM way 931312194 is one of those streets. It is not ซอย 11. That name sits on a different road, on the south side of the course, about a kilometre west of this way, and it is not attached here. No other soi name is attached either. House numbers stay out of GitHub.

This is not a live flood picture, and it is not the water level. The footer says these are the village roads, not the water level. There is no depth legend.

The page is the road geometry for the maker of the crowd-source app at <https://lakewood-water-watch.noiyo.chatgpt.site>, so those lines can be used there later. It is not a flood navigator, not a reporting app, and not a second database.

## Open the page

Open `index.html` in a browser (double-click, or any static file server). The roads are in the repo. The background map is OpenStreetMap's own tiles. There is no API key.

The line on the page is the whole claim: these are the village roads, not the water level.

## What is drawn

OpenStreetMap has the lines and almost no soi names. `data/village-roads.geojson` keeps the private residential streets through the club pin and the connected private residential roads within 400 m of 13.61523, 100.77697. Nothing farther than 2 km east of the club pin is included. Service paths, tracks, and golf-cart lines are left out.

Every road is the same thin dark color. Nothing is green, because a green line gets read as safe to drive. `data/soi-labels.json` is empty. A wrong name is worse than no name.

## Files

| File | What it is |
| --- | --- |
| `index.html` | The map |
| `data/village-roads.geojson` | The residential lines, for the other app |
| `data/soi-labels.json` | Soi names linked to a way. Empty. |
| `data/sample-not-a-reading.json` | A made-up row. Not a house, not a depth, not a report from any day. |

`data/village-roads.js` and `data/soi-labels.js` repeat those two JSON files so the page opens without a server. `scripts/check_page.py` checks that the copies match.

## Refresh the lines

```bash
python3 scripts/extract_village_roads.py
python3 scripts/check_page.py
```

Map data © OpenStreetMap contributors, available under the [Open Database License](https://www.openstreetmap.org/copyright).
