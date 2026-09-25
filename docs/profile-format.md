# Spatial profile file format

This document is the authoring reference for `cf-regions` spatial
interpretation data. It complements the machine-readable schemas and the
conceptual [profile architecture](spatial-interpretation-profiles.md).

Version 0.1 auto-discovers manifests in the bundled profile directory, a
complete external data root, or additional directories passed as
`profile_directories`/`--profile-directory`. Installed Python entry-point
plugins are intentionally not discovered yet; their packaging contract will be
finalized with that feature.

## Resource paths and identity

All paths in a profile manifest are POSIX-style paths relative to that
`manifest.json`. Paths must be relative, must not contain `..`, and identify
immutable resources. This keeps one profile-version directory portable.

`profile.id` and `profile.version` in `manifest.json` are the sole authoritative
profile identity. Directory names are an organizational convention rather than
a second registry. `hierarchy.json` is bound to its manifest by path and may
optionally be protected by SHA-256; it therefore does not repeat the profile
identity.

For the built-in default only, `profile-settings.json` necessarily refers to
that exact ID and version. Renaming the built-in profile therefore means
changing both its manifest identity and this intentional default selection;
renaming an additional profile requires changing only its manifest.

Changing geometry, hierarchy, lookup semantics, or other result-affecting data
requires a new immutable profile version.

## `manifest.json`

The authoritative schema is
[`profile-manifest.schema.json`](../src/cfregions/data/schemas/profile-manifest.schema.json).

| Field | Meaning |
| --- | --- |
| `schema_version` | File-format version understood by the loader; currently `1` |
| `profile` | Stable identity and human-facing metadata |
| `profile.id` | Stable provider-qualified profile identifier |
| `profile.version` | Immutable version of this interpretation |
| `profile.title` | Short display name |
| `profile.description` | What the profile is |
| `profile.basis` | Brief informal summary of the standards, datasets, or scientific conventions behind it |
| `profile.scope` | Intended and excluded uses |
| `profile.license` | Profile-level licensing summary; feature/source terms still apply |
| `profile.homepage` | Documentation or project URI |
| `supported_cf_versions` | Exact CF vocabulary versions for which complete coverage is claimed |
| `generated_on` | ISO date on which this immutable edition was generated |
| `crs` | Currently required to be `OGC:CRS84` |
| `lookup` | Deterministic coordinate-lookup behavior |
| `representations` | Named geometry resources such as `low` and `high` |
| `hierarchy` | Hierarchy resource, count, summary provenance, and optional digest |
| `sources` | Profile-level source and licensing bibliography |
| `limitations` | Important interpretation and fitness-for-use limitations |
| `input_sha256` | Optional hashes of pinned generation inputs |

The shared CF vocabulary hash remains mandatory in the profile-independent CF
registry. Profile authors may omit `sha256` from plain GeoJSON representations
and the hierarchy metadata. A representation that declares a compiled lookup
artifact must provide source, index, and artifact hashes so the generated data
is bound to one exact authoritative GeoJSON file. When present, these hashes bind metadata and result
provenance to exact file bytes and the loader verifies them. They are
integrity/reproducibility checks, not cryptographic signatures. An omitted hash
is exposed as `None` by the Python API and `null` in structured CLI/API output.
`input_sha256` is also optional; it records non-shipped builder inputs for
maintainers and is not read during lookup.

The currently supported lookup contract is deliberately narrow:

```json
{
  "behavior_version": "1",
  "geometry_resolution": "high",
  "default_geometry_resolution": "low",
  "area_predicate": "covers",
  "boundary_inclusive": true,
  "section_method": "minor_great_circle_distance"
}
```

`geometry_resolution` selects the representation used for coordinate lookup.
`default_geometry_resolution` selects display output when callers do not ask
for a representation. Other representations may change detail but must not
change the intended spatial interpretation.

Each representation declares:

| Field | Meaning |
| --- | --- |
| `label`, `description` | Human-facing detail information |
| `geometry_file` | Manifest-relative GeoJSON resource |
| `sha256` | SHA-256 of the exact GeoJSON bytes; optional unless `lookup_artifact` is declared |
| `feature_count` | Number of features in the complete profile resource |
| `processing.method` | Provider-defined stable processing method name |
| `processing.parameters` | Provider-defined JSON object needed to reproduce or understand that processing |
| `lookup_artifact` | Optional generated accelerator for lazy geometry access; never required to author a valid profile |

Large lookup representations may optionally declare a `lookup_artifact` with
`format: "wkb-pack-v1"`, manifest-relative `geometry_file` and `index_file`,
and mandatory `sha256`/`index_sha256` values. The parent representation's
GeoJSON `sha256` is also mandatory in this case. The artifact contains the same
geometries as the representation's GeoJSON in packed WKB plus a small bounding
box index. It does not change the profile's spatial meaning, identity, or
provenance. GeoJSON remains the portable source representation and is used
automatically when the artifact is absent. Profile authors can generate the
two files with `tools/lookup_artifact.py`; the machine-readable index contract
is [`lookup-index.schema.json`](../src/cfregions/data/schemas/lookup-index.schema.json).

## Geometry FeatureCollections

The machine-readable contract is
[`geometry.schema.json`](../src/cfregions/data/schemas/geometry.schema.json).

Each representation is a GeoJSON `FeatureCollection` in `OGC:CRS84`. Every
feature has an exact CF standardized name as both its `id` and
`properties.name`. A complete profile contains a feature for every name in each
declared supported CF release. Extra features are allowed when needed to cover
the union of several supported releases; the loader selects the exact CF
vocabulary at runtime.

Required feature properties are:

| Property | Meaning |
| --- | --- |
| `name` | Exact CF standardized region name |
| `kind` | `area` or `section` |
| `nvs_concept_url` | Concept URI corresponding to the standardized name |
| `geometry_source` | Source or derived-dataset name |
| `geometry_source_url` | Source URI; multiple URIs may be separated by `;` |
| `geometry_source_version` | Exact source or derivation version |
| `geometry_license` | Applicable geometry terms |
| `geometry_method` | How this feature was selected or constructed |
| `geometry_contexts` | Optional scientific-use contexts |
| `specificity` | Integer used only for deterministic specific-to-broad ordering |

`area` features must be `Polygon` or `MultiPolygon`; `section` features must be
`LineString` or `MultiLineString`. CF descriptions and hierarchy parents do not
belong in geometry files: descriptions come from the shared CF registry and
parents come from `hierarchy.json`.

## `hierarchy.json`

The authoritative schema is
[`hierarchy.schema.json`](../src/cfregions/data/schemas/hierarchy.schema.json).
The hierarchy is a profile-defined directed acyclic graph. Each edge has:

| Field | Meaning |
| --- | --- |
| `child`, `parent` | Exact CF names connected by the edge |
| `relation` | Currently `broader` |
| `origin` | Stable provider-defined derivation category, for example `gcmd_path_projection` |
| `source` | Name, version, URI, license, and method supporting this individual edge |
| `source_path` | Source path that directly evidences the edge, or an empty array |
| `context_path` | Optional retained source hierarchy path used for display/context even when it does not prove the edge |

All edge names are filtered to the selected CF release before validation. The
remaining graph must reference known names and must be acyclic. Semantic
hierarchy is not inferred from polygon containment.

## Discovery and validation

A profile is made available by placing its version directory beneath a scanned
profile directory. Discovery recursively finds `manifest.json` files without
opening the declared geometry or hierarchy resources. The bundled
`profile-settings.json` selects only the exact global default profile; it is not
an index of available profiles.

Loading a selected profile verifies schema versions, compatibility, hierarchy
references, duplicate edges, and cycles without opening large geometry files.
Opening a representation verifies its declared hashes, feature count, complete
name coverage, and geometry types. GeoJSON geometries are validated when used;
compiled lookup artifacts were validated by their generator and are checked
against the source representation and any declared artifact hashes.

Use the bundled default profile as a complete real-world example. For a small
synthetic example, see the external data-root fixture in
[`test_datasets.py`](../tests/test_datasets.py). It demonstrates the file
contract, but it is not advertised as an installable plugin because version
0.1 has no entry-point discovery mechanism.
