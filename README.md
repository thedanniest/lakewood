# Lakewood village roads

One page of the residential roads in Lakewood village, at Lakewood Country Club near Wat Srirattanatharam in Bang Phli, Samut Prakan. The map opens on the named streets around 13.61523, 100.77697, about a kilometre east of the club pin at 13.6104, 100.7633.

One road is labeled. OSM way 931312194 is ซอย 11, because that point lies on the line and the next private residential road is about 80 m away. The day-1 worst reading on that whole road is 95.5 cm, drawn in purple. The number on the line is 95.5 ซม., unrounded.

The other roads stay unlabeled. They are a thin dark stroke, not a water-level category. Sois 5, 7, and 9 are not labeled. A range such as 45-51 is not colored. A later label can be a sub-soi such as ซอย 15/2. None is added here. House numbers stay out of GitHub.

This is not a live flood picture. The footer says the figure is the latest water level, not which road a car can pass. Green on the scale means 0 cm. It is never described as passable.

The page is the road geometry for the maker of the crowd-source app at <https://lakewood-water-watch.noiyo.chatgpt.site>, so those lines can be used there later. It is not a flood navigator, not a reporting app, and not a second database.

## Open the page

Open `index.html` in a browser (double-click, or any static file server). The roads are in the repo. The background map is OpenStreetMap's own tiles. There is no API key.

## What is drawn

OpenStreetMap has the lines and almost no soi names. `data/village-roads.geojson` keeps the private residential streets that were already on the page, and adds the other private residential roads in that same network that come within 400 m of the named cluster. Nothing farther than 2 km east of the club pin is included. Service paths, tracks, and golf-cart lines are left out.

Unnamed lines stay thin and dark. They are not in the legend. The legend is the depth scale only: 0, 1–10, 11–20, 21–40, 41–70, and 71 ขึ้นไป. Purple is the top of that scale. The only colored line is ซอย 11.

## Files

| File | What it is |
| --- | --- |
| `index.html` | The map |
| `data/village-roads.geojson` | The residential lines, for the other app |
| `data/soi-labels.json` | ซอย 11 linked to OSM way 931312194, with the 95.5 cm reading |
| `data/sample-not-a-reading.json` | A made-up row. Not a house, not a depth, not a report from any day. |

`data/village-roads.js` and `data/soi-labels.js` repeat those two JSON files so the page opens without a server. `scripts/check_page.py` checks that the copies match.

## Refresh the lines

```bash
python3 scripts/extract_village_roads.py
python3 scripts/check_page.py
```

Map data © OpenStreetMap contributors, available under the [Open Database License](https://www.openstreetmap.org/copyright).
