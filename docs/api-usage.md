# Python API usage

The `cf-regions` distribution is imported as `cfregions`. Its public functions
use keyword-only arguments and return immutable domain objects or defensive
copies of GeoJSON data.

## Coordinate lookup

For the common case, return only the matching CF standardized region names:

```python
import cfregions

names = cfregions.match_region_names(
    longitude=-90.0,
    latitude=25.0,
)

for name in names:
    print(name)
```

Combined coordinate values are supported in either explicit order:

```python
names = cfregions.match_region_names(lonlat="-90.0, 25.0")
same_names = cfregions.match_region_names(latlon="25.0, -90.0")
```

Supply exactly one form: `longitude` with `latitude`, `lonlat`, or `latlon`.
Combined values may be comma-separated strings or two-element sequences.
Mixing forms raises `CoordinateError`.

Use `match_regions()` when provenance and match type matter:

```python
matches = cfregions.match_regions(longitude=5.0, latitude=56.0)

for match in matches:
    print(
        match.name,
        match.relation,
        match.mapping.id,
        match.mapping.version,
        match.source.name,
    )
```

`match_region_names()` is a deliberately lossy convenience wrapper around
the detailed result.

## Lookup behavior

- Coordinates use `OGC:CRS84`: longitude must be within `[-180, 180]` and
  latitude within `[-90, 90]`.
- Area lookup uses the boundary-inclusive `covers` predicate. A shared boundary
  may therefore return more than one direct match.
- Results are ordered from more specific to broader regions. Multiple valid
  matches are retained rather than reduced to one.
- `relation="covered_by"` denotes a direct area-geometry match.
- `relation="near_section"` denotes an explicitly requested proximity match to
  a diagnostic section.
- `relation="ancestor"` denotes semantic hierarchy expansion; it does not mean
  that the ancestor geometry was tested.
- `include_ancestors=False` disables semantic expansion. It does not remove
  broader regions whose own geometries directly cover the point.
- `Region.kind` and `Region.geometry_type` describe the selected spatial
  interpretation, not a geometry type defined by CF.

Some identifiers describe diagnostic passages or transects rather than areas.
They participate only when a positive proximity is requested:

```python
matches = cfregions.match_regions(
    longitude=-155.0,
    latitude=1.0,
    section_tolerance_km=5.0,
)
```

Distances to sections use spherical minor-great-circle segments.

## Public functions

| Function | Result |
| --- | --- |
| `match_region_names(...)` | Matching names as `tuple[str, ...]` |
| `match_regions(...)` | Detailed immutable `RegionMatch` objects |
| `list_spatial_profiles()` | Available profile versions |
| `list_spatial_profile_ids()` | Stable IDs of available profiles |
| `list_spatial_profile_versions(...)` | Versions for one profile ID or alias |
| `get_spatial_profile(...)` | Metadata for one profile version |
| `list_cf_versions(...)` | Available numbered CF releases |
| `list_region_names(...)` | All names for one CF release |
| `list_regions(...)` | Immutable region metadata objects |
| `list_hierarchy_edges(...)` | Complete hierarchy or one ancestor subgraph |
| `get_region(...)` | Metadata and provenance for one exact name |
| `get_region_shape(...)` | Defensive copy of one GeoJSON Feature |
| `get_dataset_info(...)` | Vocabulary, mapping, hierarchy, and limitation metadata |
| `get_catalog(...)` | Cached indexed `RegionCatalog` for advanced use |

Lookup, region, shape, hierarchy, dataset-info, and catalog functions accept
these common selections:

```python
cf_version="current"
profile="default"
profile_version="current"
data_directory=None
profile_directories=None
```

`cf_version`, `profile_version`, and `geometry_resolution` are independent.
They select the CF vocabulary, spatial interpretation, and rendering detail.
The exact resolved profile is available as `get_dataset_info().profile`.

`list_cf_versions()` is profile-independent and accepts only the optional
`data_directory`. Profile discovery functions likewise do not select a CF
release. Advanced users can load profile-independent vocabulary metadata
directly through `CFRegistry`.

## Regions, hierarchy, and shapes

```python
ancestor_edges = cfregions.list_hierarchy_edges(region_name="north_sea")

region = cfregions.get_region(
    region_name="north_sea",
    cf_version="current",
)

shape = cfregions.get_region_shape(
    region_name="north_sea",
    cf_version="current",
    geometry_resolution="high",
)
```

Shape retrieval supports `low` and `high` representations. Coordinate lookup
remains pinned to the profile's declared lookup representation, so changing
display detail does not change lookup results.

Every detailed match reports the CF release, mapping ID and version, lookup
method and predicate, optional content hash, geometry-validation mode, and
geometry or hierarchy source. The selected mode is also available as
`get_dataset_info().lookup_geometry_validation`; each representation reports
its own `validation_mode`.
Mapping versions and CF vocabulary versions are intentionally independent.

## Profiles and external data

The built-in profile has the stable ID `cfregions-default`. The aliases
`profile="default"` and `profile_version="current"` select the configured
built-in default and its current version.

`profile_directories` accepts a sequence of directories containing
self-describing profile manifests. These profiles are added without replacing
the bundled CF vocabularies or default profile:

```python
profiles = cfregions.list_spatial_profiles(
    profile_directories=["/path/to/additional-profiles"],
)
```

`data_directory` has a different purpose: it replaces the complete offline
data root, including the CF registry and profile defaults. Resources are
validated against declared counts and, when present, SHA-256 checksums.

See [Spatial interpretation profiles](spatial-interpretation-profiles.md) for
the architecture and [Spatial profile file format](profile-format.md) for the
authoring contract.

## Errors

Invalid coordinates, versions, names, resolutions, and datasets raise specific
subclasses of `cfregions.CFRegionsError`, including:

- `CoordinateError`
- `CFVersionNotFoundError`
- `RegionNotFoundError`
- `GeometryResolutionNotFoundError`
- `RegionDataError`
- `SpatialProfileNotFoundError`
- `SpatialProfileCompatibilityError`

The last error distinguishes an existing profile that does not support the
selected CF release from a profile or profile version that cannot be found.

For the scientific meaning and provenance of results, continue with
[Data sources and mapping method](data-sources-and-mapping.md) and the
[Mapping guidelines](mapping-guidelines.md).
