# Examples

`cities.geojson`: ten real cities (CRS: WGS84 lon/lat, EPSG:4326, degrees; GeoJSON order x = longitude, y = latitude).

## Source and license

- Source: the city-centre coordinates published on [Wikidata](https://www.wikidata.org/) (property P625, coordinate location), rounded to two decimals (about 1 km). Wikidata structured data is released under the [CC0 1.0 public domain dedication](https://creativecommons.org/publicdomain/zero/1.0/), so no attribution is required; it is given here for transparency.
- The values were transcribed by hand, not downloaded by a script, and are not survey data. The tested zone results do not depend on the rounding, because every city is well away from a zone boundary.
- The file itself (selection and rounding) is released under this repository's MIT license.

## Why these cities

- Bergen (5.32 E, 60.39 N) lies in the Norway exception: zone 32V, so EPSG:32632 instead of 32631.
- Ny-Ålesund (11.93 E) and Longyearbyen (15.63 E) are on Svalbard, where only zones 31, 33, 35 and 37 are used: both get 33N (EPSG:32633).
- Tromsø, Reykjavik, London, Cairo, Quito, Sydney and Wellington cover the standard formula, both hemispheres and a zone near the antimeridian (Wellington, 60S).

## Files

- `make_demo.py` writes `../docs/demo.geojson`, the tool's output for this file (shown on the [demo map](../docs/index.html)).
- `demo.ipynb` walks through the Python API on this data.
- `tests/test_examples.py` and `tests/test_notebook.py` check both offline.
