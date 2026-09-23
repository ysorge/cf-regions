# CF Regions

`cfregions` is the dependency-light, presentation-independent library for the 
mapping and lookup of [CF Standardized Region List][cf-list] names to geometries and hierarchy. 
It resolves WGS84 coordinates to region names from the CF Standardized Region List and 
exposes hierarchy, metadata, provenance, and interpreted GeoJSON geometry. 

> [!IMPORTANT]
> CF standardizes region names, not boundaries. The bundled shapes are a
> documented spatial interpretation for discovery and categorization. They are
> not official CF boundaries and must not be used for navigation or legal
> decisions.

> [!NOTE]
> **Project status: alpha.** The public API is typed and tested, but may still
> change while the project matures.

## Features

- Historical CF Standardized Region Lists, with `current` resolving to the
  latest bundled release and `list_cf_versions()` reporting what is available.
- Coordinate lookup using explicit `longitude` and `latitude` arguments in
  `OGC:CRS84`.
- Structured, provenance-rich matches that distinguish geometry matches,
  diagnostic-section proximity, and semantic hierarchy expansion.
- A queryable hierarchy graph whose edges distinguish retained GCMD path
  projections from documented mapping curation.
- Low-detail and high-detail GeoJSON representations without changing the
  deterministic lookup geometry.
- Explicit, versioned spatial interpretation profiles, with the bundled
  interpretation selected through the same provider interface intended for
  future profile packages.
- Self-describing, checksummed data manifests and optional external dataset
  directories.
- A typed Python API, conventional CLI, and fully offline runtime operation.

The distribution includes the vocabulary and geometry resources and downloads
no data during lookup.

## Requirements and installation

`cfregions` requires Python 3.10 or newer. Its only runtime dependency is
[Shapely][shapely]. Binary Shapely wheels include GEOS on common platforms.

Install from PyPI:

```console
python -m pip install cfregions
```

To work on the current source checkout instead:

```console
git clone https://github.com/ysorge/cfregions.git
cd cfregions
python -m pip install -e ".[dev]"
```

## Quick start

Arguments are keyword-only and use longitude/latitude order:

```python
import cfregions

# Get all region names covering a point:
# -------------------------------------------

names = cfregions.match_region_names(
    longitude=-90.0,
    latitude=25.0,
)
print(names) # ('gulf_of_mexico', 'atlantic_ocean', ..., 'global')

same_names = cfregions.match_region_names(lonlat="-90.0, 25.0")
print(same_names) # ('gulf_of_mexico', 'atlantic_ocean', ..., 'global')

# Get detailed matches with provenance and geometry:
# -------------------------------------------

matches = cfregions.match_regions(longitude=5.0, latitude=56.0)
for match in matches:
    print(
        match.name,
        match.relation,
        match.mapping.id,
        match.mapping.version,
    )

# Get only direct matches without semantic expansion:

direct_matches = cfregions.match_regions(
    longitude=5.0,
    latitude=56.0,
    include_ancestors=False,
)

# Get the full hierarchy graph or one region's ancestor subgraph:
# -------------------------------------------

ancestor_edges = cfregions.list_hierarchy_edges(region_name="north_sea")

region = cfregions.get_region(
    region_name="north_sea",
    cf_version="current",
)

# Get the GeoJSON shape of a region with high detail:
# -------------------------------------------

shape = cfregions.get_region_shape(
    region_name="north_sea",
    cf_version="current",
    geometry_resolution="high",
)
```

`match_region_names()` is a deliberately lossy convenience. Use
`match_regions()` whenever the mapping method and provenance matter.

## Lookup behavior

- Coordinates use `OGC:CRS84`: longitude must be within `[-180, 180]` and
  latitude within `[-90, 90]`.
- Supply exactly one coordinate form: `longitude` with `latitude`, `lonlat`, or
  `latlon`. Combined values accept comma-separated strings or two-element
  sequences; mixed forms raise `CoordinateError`.
- Area lookup uses the boundary-inclusive `covers` predicate. A shared boundary
  may therefore return more than one direct match.
- Results are ordered from more specific to broader regions. Multiple valid
  matches are retained rather than silently reduced to one.
- `relation="covered_by"` denotes a direct area-geometry match.
- `relation="near_section"` denotes an explicitly requested proximity match to
  a diagnostic section.
- `relation="ancestor"` denotes semantic hierarchy expansion; it does not claim
  that the ancestor geometry was tested.
- `include_ancestors=False` disables semantic expansion. It does not remove
  broader regions whose own geometries directly cover the queried point.
- `Region.kind` and `Region.geometry_type` describe the selected mapping
  representation, not a geometry type defined by the CF vocabulary. CF region
  names alone do not determine whether a concrete dataset means an area, line,
  or point.

Seventeen identifiers describe passages or diagnostic transects instead of
areas. They participate only when a positive proximity is requested:

```python
matches = cfregions.match_regions(
    longitude=-155.0,
    latitude=1.0,
    section_tolerance_km=5.0,
)
```

Distances to sections use spherical minor-great-circle segments.

## Python API

| Function | Result |
| --- | --- |
| `match_region_names(...)` | Matching names as `tuple[str, ...]` |
| `match_regions(...)` | Detailed immutable `RegionMatch` objects |
| `list_spatial_profiles()` | Available profile versions |
| `list_spatial_profile_ids()` | Stable IDs of available profiles |
| `list_spatial_profile_versions(...)` | Available versions for one profile ID or alias |
| `get_spatial_profile(...)` | Metadata for one selected profile version |
| `list_cf_versions(...)` | Available numbered CF releases |
| `list_region_names(...)` | All names for one release |
| `list_regions(...)` | Immutable region metadata objects |
| `list_hierarchy_edges(...)` | Full hierarchy graph or one region's ancestor subgraph |
| `get_region(...)` | Metadata and provenance for one exact name |
| `get_region_shape(...)` | A defensive copy of one GeoJSON Feature |
| `get_dataset_info(...)` | Vocabulary, mapping, hierarchy, and limitation metadata |
| `get_catalog(...)` | Cached indexed `RegionCatalog` for advanced use |

Lookup, region, shape, hierarchy, info, and catalog functions accept:

```python
cf_version="current"
profile="default"
profile_version="current"
data_directory=None
profile_directories=None
```

`cf_version`, `profile_version`, and `geometry_resolution` are independent:
they select the vocabulary, the scientific interpretation, and rendering
detail respectively. The resolved exact profile is available as
`get_dataset_info().profile`.

`profile_directories` is an optional sequence of directories containing
self-describing profile manifests. They extend the built-in profiles without
replacing the bundled CF vocabularies or default profile.

`list_cf_versions()` is intentionally profile-independent and accepts only the
optional `data_directory`. `list_spatial_profiles()` and
`get_spatial_profile()` likewise do not select a CF release. Advanced users can
load profile-independent vocabulary metadata directly through `CFRegistry`.

Invalid coordinates, versions, names, resolutions, and datasets raise specific
subclasses of `cfregions.CFRegionsError`, including `CoordinateError`,
`CFVersionNotFoundError`, `RegionNotFoundError`,
`GeometryResolutionNotFoundError`, and `RegionDataError`.
An unavailable profile or profile version raises `SpatialProfileNotFoundError`.
An available profile combined with an unsupported CF release raises
`SpatialProfileCompatibilityError`.

## Command-line interface

The CLI mirrors the Python argument names:

```console
cfregions --version
cfregions profiles
cfregions versions
cfregions lookup --longitude -90 --latitude 25 --cf-version current
cfregions lookup --lonlat "7.990654, 24.602804"
cfregions lookup --latlon "24.602804, 7.990654"
cfregions lookup --lonlat "5, 56" --no-ancestors
cfregions lookup --lonlat "7.990654, 24.602804" --format table
cfregions lookup --longitude 5 --latitude 56 --format json
cfregions lookup --longitude 5 --latitude 56 --format jsonl
cfregions regions --cf-version 1 --format json
cfregions hierarchy north_sea
cfregions hierarchy --format jsonl
cfregions shape north_sea --geometry-resolution high --format geojson --output north-sea.geojson
cfregions shape north_sea --format wkt --output north-sea.wkt
cfregions shape north_sea --format wkb --output north-sea.wkb
cfregions info --cf-version current
cfregions info --profile cfregions-default --profile-version current
```

Lookup and region-list commands provide four deliberately distinct formats:

| Format | Intended use |
| --- | --- |
| `names` | Default; one region name per line, suitable for shell pipelines |
| `table` | Compact human-readable columns; not intended as a parsing contract |
| `json` | One complete structured document, including query and provenance |
| `jsonl` | One complete match or region object per line for streaming tools |

For example:

```console
cfregions lookup --lonlat "7.990654, 24.602804" | while IFS= read -r region; do
    printf '%s\n' "$region"
done

cfregions lookup --lonlat "7.990654, 24.602804" --format jsonl \
    | jq -r 'select(.relation == "covered_by") | .name'
```

`python -m cfregions` is equivalent to the `cfregions` command. Use
`cfregions COMMAND --help` for command-specific options. Standard output
contains only the selected data format. Command errors are written to standard
error and return exit status 2.

### Hierarchy output

`cfregions hierarchy` displays the complete mapping hierarchy. Supplying a
region name limits it to that region's ancestor subgraph. The default `tree`
view labels links as `GCMD` or `curated`; `table`, `json`, and `jsonl` provide
lossless child-to-parent edges. The graph may have multiple parents and is not
necessarily a tree.

An edge is a `gcmd_path_projection` only when its parent is evidenced by the
retained GCMD path. Other global, composite, or section-connectivity links are
reported as `mapping_curation` rather than being attributed to NASA.

### Shape output

`shape` supports these formats without optional geospatial dependencies:

| Format | Content |
| --- | --- |
| `geojson` | Default GeoJSON Feature, including region and mapping metadata |
| `wkt` | OGC Well-Known Text geometry |
| `wkb` | Binary OGC Well-Known Binary, suitable for files and pipelines |
| `wkb-hex` | Text-safe hexadecimal WKB |

All geometries use `OGC:CRS84`. WKT and WKB contain only geometry and do not
embed CRS or provenance, so retain that information separately. SVG is not an
exchange format here: it is a drawing representation without geospatial CRS
semantics. GeoPackage or Shapefile export would require a substantially heavier
GDAL-based optional dependency and is intentionally outside the core package.

## Spatial interpretation profiles

The default profile has the stable ID
`cfregions-default`. Omitting `profile` selects the
`default` alias; omitting `profile_version` selects its `current` alias. Exact
resolved identities are always reported in structured provenance.

Profiles are declarative and self-describing. The shared `catalog.json` and
`versions/` manifests describe CF vocabularies independently of any spatial
interpretation. Profile manifests below `profiles/` are auto-discovered; the
small `profile-settings.json` file contains only the exact built-in default.
IDs, versions, and manifest paths are not repeated in an index. A provider
protocol and deterministic multi-provider resolver support additive profile
directories and form the extension boundary for future installed profile
packages. Version 0.1 does not discover third-party Python entry points yet.

The format and planned extension contract are documented in [Spatial
interpretation profiles][spatial-profiles]. The field-level authoring contract
is in [Spatial profile file format][profile-format].

## Versions and external datasets

`current` is an explicit alias in the bundled catalog rather than a network
lookup. Version selection is therefore reproducible and works offline.

An external `data_directory` can use the same separated CF-registry and
profile-registry layout as the bundled [`data` directory][data-directory]. The
CLI exposes the same option as `--data-directory`. It is a complete offline data
root, not the future single-profile plugin mechanism; it may contain multiple
profiles, and normal profile selection still applies. Resources are validated
against declared counts and SHA-256 digests before use. No mutable process-wide
dataset configuration is used.

For the usual extension case, pass one or more `profile_directories` in Python
or repeat `--profile-directory PATH` on the CLI. Their manifests are discovered
additively, while the selected CF registry and built-in default profile remain
available. Profile-relative geometry and hierarchy paths make each version
directory independently portable.

## Provenance and geometry representations

Every detailed match reports the CF release, mapping ID and version, lookup
method and predicate, content hash, and geometry or hierarchy source. Mapping
versions and CF vocabulary versions are intentionally independent.

Shape retrieval supports `low` (compact and fast) and `high` (larger and more
detailed) representations. Coordinate lookup remains pinned to the mapping's
declared low representation, so changing rendering detail cannot change query
results. Both representations preserve the selected upstream definitions. For
example, the SeaVoX North Sea and Baltic Sea interpretations do not touch, and
the project does not insert an undocumented connector.

The complete design and validation rules are in the
[mapping guidelines][mapping-guidelines]. The concrete source roles and lookup
pipeline are described in [Data sources and mapping method][data-sources]. The
operational process for new CF releases and profile editions is in
[Dataset maintenance][dataset-maintenance]. Licenses, required attributions,
and legal notices are listed separately in [Data licenses][data-licenses].

## Development and support

Install the development dependencies and run the core checks:

```console
python -m pip install -e ".[dev]"
ruff check src tests tools
mypy src
pytest
python -m build
twine check dist/*
```

Report bugs and request features through [GitHub Issues][issues]. Report
security vulnerabilities privately as described in the [security
policy][security].

## Contributing

Contributions are welcome through issues and pull requests. For substantial
features, API changes, or new spatial interpretations, please open an issue
first so the approach and scope can be discussed. Small fixes and documentation
improvements may be submitted directly. See the project's [contribution
guide][contributing] and [Code of conduct][code-of-conduct] before
contributing.

## Authors and maintainership

`cfregions` was initiated and originally developed by [Yves Sorge](https://github.com/ysorge) 
during the [CF Conventions Community Workshop 2026][workshop] at ECMWF in Bonn, Germany. The project is currently maintained by its original author.

Additional contributors are recorded in [AUTHORS.md](AUTHORS.md) and the 
repository history. Maintainer responsibility may move to another person or 
organization without replacing the authorship of existing contributions.

## License

The `cfregions` source code is licensed under the [Apache License
2.0][license] (`Apache-2.0`). Bundled data is not relicensed under Apache-2.0
and retains the terms documented in [Data licenses][data-licenses]. Downstream
users must preserve the applicable source notices and attributions.

[cf-list]: https://cfconventions.org/Data/standardized-region-list/standardized-region-list.current.html
[code-of-conduct]: https://github.com/ysorge/cfregions/blob/main/CODE_OF_CONDUCT.md
[contributing]: https://github.com/ysorge/cfregions/blob/main/CONTRIBUTING.md
[data-directory]: https://github.com/ysorge/cfregions/tree/main/src/cfregions/data
[data-licenses]: https://github.com/ysorge/cfregions/blob/main/DATA_LICENSES.md
[data-sources]: https://github.com/ysorge/cfregions/blob/main/docs/data-sources-and-mapping.md
[dataset-maintenance]: https://github.com/ysorge/cfregions/blob/main/docs/dataset-maintenance.md
[issues]: https://github.com/ysorge/cfregions/issues
[license]: https://github.com/ysorge/cfregions/blob/main/LICENSE
[mapping-guidelines]: https://github.com/ysorge/cfregions/blob/main/docs/mapping-guidelines.md
[profile-format]: https://github.com/ysorge/cfregions/blob/main/docs/profile-format.md
[project]: https://github.com/ysorge/cfregions
[security]: https://github.com/ysorge/cfregions/blob/main/SECURITY.md
[shapely]: https://shapely.readthedocs.io/
[spatial-profiles]: https://github.com/ysorge/cfregions/blob/main/docs/spatial-interpretation-profiles.md
[workshop]: https://cfconventions.org/Meetings/2026-Workshop.html
