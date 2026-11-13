# utm-zone-finder

Find the right UTM zone and EPSG code for a latitude/longitude, a bounding box
or a GeoJSON file, including the Norway and Svalbard exceptions.

Picking `floor((lon + 180) / 6) + 1` is right almost everywhere, but wrong for
southwest Norway (zone 32 instead of 31) and Svalbard (only zones 31, 33, 35
and 37 are used). This small, dependency-free package handles those cases and
also reports which zones a larger extent spans.

## Install

```bash
pip install git+https://github.com/AmmarYasser455/utm-zone-finder
```

Requires Python 3.10+. No runtime dependencies.

## Command line

```console
$ utm-zone-finder point 60 5          # Bergen, Norway
UTM zone 32N  EPSG:32632  central meridian 9

$ utm-zone-finder bbox -1 50 1 52     # min_lon min_lat max_lon max_lat
UTM zone 31N  EPSG:32631  central meridian 3
Spans zones: 30N (EPSG:32630), 31N (EPSG:32631)
```

```console
$ utm-zone-finder point 78 15 --json   # Svalbard
{
  "number": 33,
  "hemisphere": "N",
  "epsg": 32633,
  "central_meridian": 15,
  "polar": false,
  "name": "33N"
}
```

```console
$ utm-zone-finder geojson area.geojson
```

Invalid input (out-of-range, NaN or infinite coordinates, malformed GeoJSON or
JSON, unreadable files) prints `error: ...` to stderr and exits with status 2.
The Python API raises `ValueError` for the same cases (and `OSError` for files
that cannot be opened).
`python -m utm_zone_finder ...` works too.

## Python

```python
from utm_zone_finder import zone_for_point, zone_for_bbox, zone_for_geojson, zones_spanned

z = zone_for_point(60, 5)
z.epsg, z.name        # (32632, '32N')

zone_for_bbox(-1, 50, 1, 52).epsg                 # 32631
[z.name for z in zones_spanned(-1, 50, 1, 52)]    # ['30N', '31N']
zone_for_geojson("area.geojson")                  # path or parsed dict
```

## Limitations

- Only WGS84 longitude/latitude input is supported.
- For a bbox or GeoJSON file the zone of the bounding-box centre is returned;
  data spanning several zones is listed but not split. `zones_spanned` samples
  a 0.5 degree grid, so a sliver narrower than that could be missed.
- Extents crossing the antimeridian are not handled (min_lon must be <= max_lon).
- Latitudes beyond 80S / 84N are outside UTM; a zone is still returned with
  `polar: true` (UPS would be the proper system there). For a bbox or GeoJSON
  extent the flag is set if any part of the extent lies beyond that range.
- Only the Norway and Svalbard exceptions are applied; other national or
  local preferences are not.
- GeoJSON coordinates beyond the first two values (e.g. altitude) must be
  finite numbers but are otherwise ignored.
- GeoJSON structure is checked (string `type`, coordinate nesting per geometry
  type, minimum positions per line/ring, allowed collection members), but
  ring closure, winding order and self-intersection are not checked, and
  foreign members and `crs` are ignored.

## License

MIT, see [LICENSE](LICENSE).
