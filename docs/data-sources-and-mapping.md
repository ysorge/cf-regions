# Data sources and mapping method

## Scope

`cf-regions` connects controlled names from the CF Standardized Region List to a
versioned spatial interpretation. CF defines the names and a small number of
descriptions, but it does not define canonical boundaries. The polygons and
lines distributed by this project are therefore not official CF geometries.

This document explains which source has which role and how a coordinate becomes
a set of matches. It describes the bundled spatial interpretation profile. The normative rules
for creating mappings are in [Mapping guidelines](mapping-guidelines.md), and
the profile selection and extension model is in [Spatial interpretation
profiles](spatial-interpretation-profiles.md). The
license terms and required attribution are in
[Data licenses and attribution](../DATA_LICENSES.md).

The exact profile identity, input hashes, processing parameters, source list,
and limitations for a release are recorded in its profile manifest. Exact
per-region source versions, URLs, licenses, and derivation details are embedded
in every GeoJSON feature. Those machine-readable records take precedence over
this overview.

## Four independent identities

The following versions answer different questions and must not be conflated:

| Identity | Meaning | Example |
| --- | --- | --- |
| CF vocabulary version | Which standardized names and descriptions exist? | CF Standardized Region List v5 |
| Spatial profile version | Which spatial interpretation and lookup behavior are used? | `cfregions-default@2026.09.1` |
| Geometry resolution | Which rendering detail is requested within the profile? | `low` or `high` |
| Package version | Which implementation and bundled data were installed? | the installed `cf-regions` release |

An upstream source version is a fourth identity. A mapping may combine several
upstream releases and may be reused by more than one CF vocabulary version when
it contains geometry for every name in those vocabularies.

## Source roles

| Source | Role in the bundled mapping | What it does not define |
| --- | --- | --- |
| CF Standardized Region List | Exact identifiers and descriptions | Boundaries or point-in-region behavior |
| NASA GCMD Location Keywords | Retained semantic location paths used to evidence some hierarchy links | Polygon geometry and all project hierarchy links |
| SeaVoX Salt and Fresh Water Body Gazetteer | Selected and dissolved polygons for oceans and named marine areas | Land regions and diagnostic sections |
| Natural Earth | Generalized continents, land/ocean masks, lakes, selected geographic regions, and the contiguous United States | Authoritative legal or navigational boundaries |
| OMIP protocol | Approximate endpoints for ocean diagnostic sections | Enclosed area polygons |
| CMIP6 CMOR tables | Additional diagnostic-section definitions and contexts | General marine-area boundaries |
| Project-authored rules | Analytical world/hemisphere extents, composites, source selection, hierarchy curation, and deterministic processing | A claim of CF or upstream authority |

Source selection is deliberate rather than fallback-based. For example, the
South China Sea uses a pinned Natural Earth marine feature because the selected
SeaVoX edition does not provide a directly usable exact feature. Composite
regions such as `atlantic_arctic_ocean` are explicit unions, while
`indo_pacific_ocean` is a documented project interpretation of the CF
description. These choices are stored as each feature's `geometry_method`.

## Why some region names are sections instead of areas

CF does not classify standardized region names as polygons or lines. A name
such as `denmark_strait` identifies a geographic concept, but the CF list
provides neither an area boundary nor a required geometry type. In the current
CF list, `denmark_strait` also has no description that would resolve this
choice.

### How a CF user determines the intended geometry

The standardized name alone is insufficient. In a concrete CF dataset, inspect
the metadata surrounding the region label:

1. A CF geometry container is decisive when present: its `geometry_type`
   explicitly says `point`, `line`, or `polygon`, and its node coordinates
   define the geometry used by that dataset.
2. Otherwise, inspect coordinate variables, bounds, and the data variable's
   `standard_name`, dimensions, and `cell_methods`. A transport *across a line*
   and a mean *over an area* use a region label in different contexts.
3. Consult the experiment or data-product specification. CMIP/OMIP transport
   tables, for example, define named diagnostic sections independently of the
   CF region vocabulary.
4. If none of this information exists, the dataset does not provide enough
   information to decide whether the name denotes a point, line, or area. Do
   not infer a geometry type from the spelling of the name.

The CF `region` variable standardizes label values; it does not attach a
geometry type to every label. CF can encode explicit point, line, and polygon
geometries, but that geometry belongs to the individual dataset, not to the
Standardized Region List itself.

Correspondingly, the `kind` and `geometry_type` fields returned by `cf-regions`
describe the selected **mapping representation**. They are not properties
asserted by CF. A result should be read as "the bundled mapping represents
`denmark_strait` as a diagnostic section", not "CF defines Denmark Strait as a
line".

The bundled mapping represents 17 names as diagnostic sections because they
entered climate-model workflows as coordinate values for transports across
pre-defined transects. The OMIP protocol defines these diagnostics as mass
transport through sections and supplies approximate endpoints. The project uses
those referenced transects rather than inventing area boundaries.

For example, `denmark_strait` is a `LineString` from approximately
`(-37.0, 66.1)` to `(-22.5, 66.0)`, taken from OMIP Table J1. This geometry
means "the diagnostic transect used to calculate transport across Denmark
Strait". It does not mean that the physical strait has zero width or that an
area interpretation would be invalid.

The current section set is:

| Basis | CF region names |
| --- | --- |
| OMIP Table J1 | `barents_opening`, `bering_strait`, `davis_strait`, `denmark_strait`, `drake_passage`, `english_channel`, `faroe_scotland_channel`, `florida_bahamas_strait`, `gibraltar_strait`, `iceland_faroe_channel`, `indonesian_throughflow`, `mozambique_channel`, `pacific_equatorial_undercurrent`, `taiwan_luzon_straits`, `windward_passage` |
| CMIP6 CMOR tables | `canadian_archipelago` |
| OMIP and CMIP6 variants | `fram_strait` |

This is a mapping-profile decision, not a naming rule. A name containing
`strait`, `channel`, `passage`, or `opening` is not automatically a line. A
different scientifically justified mapping could provide an area polygon for
the same CF concept. Such a mapping would need its own identifier/version and
source provenance; it must not silently replace the diagnostic-section meaning
inside the current mapping edition.

Section geometry has deliberately different lookup behavior:

- it never participates in ordinary point-in-polygon lookup;
- it is considered only when `section_tolerance_km` is positive;
- a result is reported as `relation="near_section"`, with its distance;
- the endpoints are approximate and may differ from the optimal transect on a
  particular model grid.

The scientific basis is Appendix J and Table J1 of Griffies et al. (2016),
[OMIP contribution to CMIP6](https://doi.org/10.5194/gmd-9-3231-2016). The
historical CF discussion also records that these strait and channel names were
added for CMIP transport-coordinate use:
[CF metadata discussion](https://cfconventions.org/mailing-list-archive/Data/4911.html).

## From sources to the bundled dataset

The maintainer-only builder performs this pipeline offline from explicitly
provided, pinned input files:

```text
CF XML -------------------------> names and descriptions
GCMD Location CSV -------------> retained hierarchy paths
SeaVoX / Natural Earth --------> area source geometries
OMIP / CMIP6 ------------------> diagnostic section lines
project profile rules ---------> selection, unions, hierarchy and analytical shapes
                                      |
                                      v
                              validated feature set
                                      |
                         +------------+------------+
                         |                         |
                    low GeoJSON                high GeoJSON
                    lookup input               display detail
                         |                         |
                         +------------+------------+
                                      |
                profile manifest and hierarchy with checksums
```

The low and high representations express the same interpretation. They differ
only in simplification and coordinate precision. Coordinate lookup is pinned to
the representation named by `lookup.geometry_resolution` in the profile manifest;
requesting a high-detail display shape cannot change lookup results.

The builder validates exact coverage of its target CF release, pinned Natural
Earth layer versions, source selections, non-empty geometry, and input hashes.
The runtime loader independently validates manifests, mandatory vocabulary and
declared profile hashes, vocabulary version/date/count, geometry coverage,
geometry types, hierarchy references, and hierarchy acyclicity.

## How coordinate lookup works

For `match_regions()` and `cfregions lookup`, the bundled profile applies the
following deterministic steps:

1. Resolve exactly one coordinate form and validate longitude and latitude.
   Coordinates are interpreted in `OGC:CRS84`, in longitude/latitude order.
2. Independently load the selected CF vocabulary and compatible profile
   manifest.
3. Query the profile manifest's lookup geometry representation with a spatial
   index.
4. For every candidate area, apply Shapely's boundary-inclusive `covers`
   predicate. A shared boundary may therefore produce more than one direct
   match.
5. Do not match diagnostic section lines by default. When
   `section_tolerance_km` is positive, compute spherical minor-great-circle
   distance to each section and return those inside the requested tolerance.
6. Unless `include_ancestors=False` or `--no-ancestors` is selected, traverse
   the semantic parent graph and add connected parent names as
   `relation="ancestor"`.
7. Return every valid result in deterministic, specific-to-broad order. The
   order never discards overlapping or otherwise ambiguous matches.

Direct area and section matches identify the source geometry and method that
caused the match. Hierarchy-expanded results are explicitly marked as semantic,
not geometric. The separate hierarchy API exposes each child-to-parent edge and
states whether it is evidenced by a retained GCMD path or by documented mapping
curation.

Disabling ancestor expansion removes only generated `ancestor` results. A broad
region such as `global_ocean` may remain when its own polygon directly covers
the coordinate; that result is then correctly reported as `covered_by`.

## Reading provenance

Detailed Python, JSON, JSONL, REST, and GeoJSON results expose the provenance
needed to understand a match:

- `cf_version`: vocabulary used for the name;
- `mapping.id` and `mapping.version`: spatial interpretation used;
- `relation`, `method`, and `predicate`: how the result was obtained;
- `source.name`, `source.version`, `source.uri`, and `source.license`: upstream
  basis for a direct match;
- `geometry_source` and `geometry_method`: corresponding fields on an exported
  shape;
- geometry resolution, CRS, generation date, and content hash.

For example:

```python
import cfregions

for match in cfregions.match_regions(lonlat=(5.0, 56.0)):
    print(
        match.name,
        match.relation,
        match.mapping.version,
        match.source.name,
        match.method,
    )

feature = cfregions.get_region_shape(region_name="north_sea")
print(feature["properties"]["geometry_source"])
print(feature["properties"]["geometry_method"])
```

The same information can be inspected from the CLI without relying on a
human-readable table:

```console
cfregions lookup --lonlat "5, 56" --format jsonl
cfregions shape north_sea --format geojson
cfregions hierarchy north_sea --format json
cfregions info --format json
```

## Canonical data files

The bundled registry is self-describing:

```text
data/catalog.json
  -> data/versions/<cf-version>.json
       -> exact vocabulary XML and SHA-256

data/profile-settings.json
  -> exact built-in default profile identity only

data/profiles/<profile-id>/<profile-version>/manifest.json (auto-discovered)
       -> low/high GeoJSON and SHA-256
       -> hierarchy.json and SHA-256
       -> supported CF versions, lookup behavior, sources, and limitations
```

The geometry files deliberately contain the complete feature set for their
profile edition. At load time, the registry selects the features present in the
requested CF vocabulary and replaces feature descriptions with those from that
exact vocabulary release.

## Known limitations

- Geometry is generalized and must not be used for navigation or legal
  boundaries.
- Valid interpretations may overlap or leave gaps. Such outcomes are not
  silently repaired.
- Diagnostic sections are approximate lines and require an explicit tolerance.
- Semantic hierarchy and geometric containment are different relationships.
- The bundled provider currently exposes one spatial interpretation profile.
  Additional profile directories are auto-discovered through the API and CLI
  without replacing the built-in default or shared CF registry. A
  self-describing `data_directory` remains a complete data-root override.
