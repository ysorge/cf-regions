# Command-line usage

The `cfregions` command provides the same coordinate, CF-version, and spatial-
profile selections as the Python API.

## Quick start

Look up a longitude/latitude pair and print one matching name per line:

```console
cfregions lookup --lonlat "5, 56"
```

For a compact human-readable table or structured JSON:

```console
cfregions lookup --lonlat "5, 56" --format table
cfregions lookup --lonlat "5, 56" --format json
```

Use the built-in help to discover commands and options:

```console
cfregions --help
cfregions lookup --help
```

`python -m cfregions` is equivalent to the `cfregions` command.

## Commands

| Command | Purpose |
| --- | --- |
| `lookup` | Resolve one coordinate to matching region names |
| `regions` | List region names or metadata for a CF release |
| `hierarchy` | Show the complete hierarchy or one ancestor subgraph |
| `shape` | Export one region geometry |
| `profiles` | Discover spatial interpretation profiles |
| `versions` | List available CF Standardized Region List versions |
| `info` | Show selected dataset, profile, and provenance metadata |

Examples:

```console
cfregions --version
cfregions profiles
cfregions versions
cfregions lookup --longitude -90 --latitude 25 --cf-version current
cfregions lookup --lonlat "7.990654, 24.602804"
cfregions lookup --latlon "24.602804, 7.990654"
cfregions lookup --lonlat "5, 56" --no-ancestors
cfregions regions --cf-version 1 --format json
cfregions hierarchy north_sea
cfregions info --cf-version current
```

## Coordinate forms

Supply exactly one coordinate form:

- `--longitude VALUE` together with `--latitude VALUE`
- `--lonlat "LONGITUDE, LATITUDE"`
- `--latlon "LATITUDE, LONGITUDE"`

Using more than one form is ambiguous and returns an error. Coordinates use
`OGC:CRS84`; longitude is in `[-180, 180]` and latitude in `[-90, 90]`.

## Output formats

Lookup and region-list commands provide four distinct formats:

| Format | Intended use |
| --- | --- |
| `names` | Default; one name per line, suitable for shell pipelines |
| `table` | Compact human-readable columns; not a parsing contract |
| `json` | One complete structured document, including provenance where applicable |
| `jsonl` | One match or region object per line for streaming tools |

For example:

```console
cfregions lookup --lonlat "7.990654, 24.602804" | while IFS= read -r region; do
    printf '%s\n' "$region"
done

cfregions lookup --lonlat "7.990654, 24.602804" --format jsonl \
    | jq -r 'select(.relation == "covered_by") | .name'
```

Standard output contains only the selected data format. Errors are written to
standard error and return exit status 2.

## Hierarchy output

`cfregions hierarchy` displays the complete mapping hierarchy. Supplying a
region name limits the result to that region's ancestor subgraph:

```console
cfregions hierarchy north_sea
cfregions hierarchy --format jsonl
```

The default `tree` view labels links as `GCMD` or `curated`. The `table`,
`json`, and `jsonl` formats provide lossless child-to-parent edges. The graph
may have multiple parents and is not necessarily a tree.

An edge is a `gcmd_path_projection` only when its parent is evidenced by the
retained GCMD path. Other global, composite, or section-connectivity links are
reported as `mapping_curation` rather than attributed to NASA.

## Shape output

Export a region geometry to standard output or a file:

```console
cfregions shape north_sea --geometry-resolution high --format geojson \
    --output north-sea.geojson
cfregions shape north_sea --format wkt --output north-sea.wkt
cfregions shape north_sea --format wkb --output north-sea.wkb
```

| Format | Content |
| --- | --- |
| `geojson` | GeoJSON Feature with region and mapping metadata |
| `wkt` | OGC Well-Known Text geometry |
| `wkb` | Binary OGC Well-Known Binary for files and pipelines |
| `wkb-hex` | Text-safe hexadecimal WKB |

All geometries use `OGC:CRS84`. WKT and WKB contain geometry only and do not
embed CRS or provenance, so retain that information separately. SVG is not a
geospatial exchange format. GeoPackage and Shapefile export would require a
substantially heavier GDAL-based dependency and are intentionally outside the
core package.

## Versions, profiles, and data directories

Select an exact CF release or spatial profile when reproducibility matters:

```console
cfregions lookup --lonlat "5, 56" --cf-version 5
cfregions info --profile cfregions-default --profile-version 2026.09.1
```

The `current` aliases are convenient for interactive use. Structured output
reports the exact resolved CF and profile versions.

Additional profile directories retain the built-in data and default profile:

```console
cfregions profiles --profile-directory /path/to/additional-profiles
cfregions lookup --lonlat "5, 56" \
    --profile-directory /path/to/additional-profiles \
    --profile my-profile \
    --profile-version 1
```

`--profile-directory` is repeatable. By contrast, `--data-directory` replaces
the complete data root, including the CF registry and profile defaults.

For result semantics and the full Python interface, see
[Python API usage](api-usage.md). Profile authors should continue with
[Spatial interpretation profiles](spatial-interpretation-profiles.md).
