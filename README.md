# Lakewood village roads

One page of the residential roads in Lakewood village, at Lakewood Country Club near Wat Srirattanatharam in Bang Phli, Samut Prakan. The map is centered on the club pin at 13.6104, 100.7633.

These are unlabeled village roads. This is not a live flood picture, and it is not the water level. Real readings stay out of GitHub.

The page is the road geometry for the maker of the crowd-source app at <https://lakewood-water-watch.noiyo.chatgpt.site>, so those lines can be used there later. It is not a flood navigator, not a reporting app, and not a second database.

## Open the page

Open `index.html` in a browser (double-click, or any static file server). The roads are in the repo. The background map is OpenStreetMap. There is no API key and nothing here is deployed.

The line on the page is the whole claim: these are the village roads, not the water level.

## What is drawn

OpenStreetMap has the lines and almost no soi names. The file `data/village-roads.geojson` keeps `highway=residential` ways tagged `access=private` that connect through the club pin. That is the gated village. One roundabout at the north edge, and the three streets on it, sit a few metres short of a shared node, so they are included too. Service paths, tracks, and golf-cart lines are left out, and so are the public roads of the neighboring estates.

Every road is one neutral color. Nothing is green, because a green line gets read as safe to drive.

Soi names are not attached yet. `data/soi-labels.json` is empty. Geocoding "Soi Mu Ban Lake Wood" plus a number did not return a point in the village: Nominatim had no match, and a worldwide match landed on a building in Canada, which was rejected. Where sois 5, 7, and 9 sit on top of each other, those stay unlabeled. A wrong name is worse than no name. It is fine that this first page has zero labels. A label, when one is earned, is short Thai such as `ซอย 7`, not the long English name.

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
