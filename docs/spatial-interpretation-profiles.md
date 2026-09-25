# Spatial interpretation profiles

## Purpose

CF standardizes region names and descriptions, but does not publish canonical
boundaries or a normative line-versus-area classification. A **spatial
interpretation profile** is therefore a versioned, citable, and reproducible
mapping from CF concepts to geometries, hierarchy relations, and lookup
behavior for a stated purpose.

The bundled profile is `cfregions-default`. It is a project-supplied
interpretation, not an official CF geometry.

## Independent CF and profile data

The data model intentionally has two independent parts:

```text
data/
├── catalog.json                         CF release discovery
├── versions/<cf-version>.json           CF release metadata
├── vocabularies/*.xml                   original CF vocabularies
├── schemas/                             schemas for both contracts
├── profile-settings.json                exact built-in default only
└── profiles/
    └── <profile-id>/
        └── <profile-version>/
            ├── manifest.json            profile identity, behavior, provenance
            ├── hierarchy.json           profile-defined broader relations
            └── geometry/
                ├── low.geojson
                ├── high.geojson         optional representation
                ├── high.lookup.json     optional generated index
                └── high.lookup.wkb      optional generated geometry pack
```

The CF registry is shared by every profile. A profile provider must **not**
copy or republish CF XML, `catalog.json`, or `versions/` manifests. Its profile
manifest declares `supported_cf_versions`; at runtime `cf-regions` selects a CF
release and a profile independently, verifies compatibility, and then verifies
that the profile supplies geometry for every name in that release.

The four version axes have different meanings:

| Selection | Meaning |
| --- | --- |
| `cf_version` | Names and descriptions from one CF release |
| `profile` and `profile_version` | Spatial meaning, hierarchy, and lookup behavior |
| `geometry_resolution` | Rendering detail within that profile version |
| package version | Installed Python implementation and bundled artifacts |

Changing rendering resolution must not change coordinate-lookup results.

## What makes a complete profile

A profile version consists of the following profile-owned resources:

- `manifest.json`, including its stable ID/version, intended scope, supported
  CF releases, lookup semantics, representations, sources, limitations, and
  optional checksums;
- at least one GeoJSON representation containing the profile's geometry and
  feature-level geometry provenance;
- `hierarchy.json`, containing explicit child-to-parent edges and provenance
  for each edge.

A representation may additionally ship a generated lookup artifact for faster
lazy access. It is an optimization only: profiles remain complete and usable
without it, and contributors do not need to author binary data by hand.

Hierarchy is profile-dependent. This matters for political groupings,
scientific basin subdivisions, composite oceans, and diagnostic sections: two
valid interpretations may use different broader relations even while sharing
the same CF vocabulary.

The geometry files consequently do not define CF descriptions or hierarchy
parents. CF descriptions come from the selected vocabulary; parents come from
the selected profile's `hierarchy.json`.

Representation processing is described as a profile-defined `method` plus a
parameter object. The core does not require SeaVoX- or Natural-Earth-specific
fields from other providers.

The exact manifest, GeoJSON-feature, hierarchy-edge, path, and validation
contracts are documented in [Spatial profile file format](profile-format.md).

## Discovery and provider boundary

Profiles are discovered automatically from `manifest.json` files below each
configured profile directory. The manifest is the sole authoritative source of
its profile ID and version; no central index repeats those values or the
manifest path. Only the deliberate global default is configured separately:

```json
{
  "schema_version": 1,
  "default_profile": {
    "id": "cfregions-default",
    "version": "2026.09.1"
  }
}
```

Geometry and hierarchy paths are relative to the manifest. Discovery reads
only small JSON manifests; geometry and hierarchy data stay lazy until a
profile is selected. Providers may add SHA-256 values for integrity checking,
but checksums are not required for plain GeoJSON profiles. If a representation
declares a compiled lookup artifact, hashes for its authoritative GeoJSON,
index, and WKB pack are required to prevent stale or mismatched generated data.

An additional directory may contain one or many profile versions, conventionally:

```text
additional-profiles/
└── <profile-id>/
    └── <profile-version>/
        ├── manifest.json
        ├── hierarchy.json
        └── geometry/
```

The directory names are not parsed as identity. If one profile ID has multiple
discovered versions, callers should select `profile_version` explicitly;
`current` is automatic only for the exact configured built-in default or when a
provider exposes one version of that ID.

At runtime the layers are:

```text
CFRegistry -> CFRelease ───────────────┐
                                       ├─> DatasetBundle -> RegionCatalog
SpatialProfileResolver                │
  -> SpatialProfileProvider           │
       -> SpatialProfileDataset ──────┘
```

`SpatialProfileProvider` is a small protocol rather than a base class. Version
0.1 combines the bundled provider (or the equivalent provider in a complete
external `data_directory`) with zero or more auto-discovered
`profile_directories`. It does not yet scan Python entry points.
A future release can discover providers from a namespaced entry-point group
such as `cfregions.spatial_profiles`; such a provider will expose only its own
profile manifests and resources and rely on the shared `CFRegistry` for CF
data.

This distinction also explains two deployment forms:

- a future profile plugin/package supplies profile resources only;
- `profile_directories`/repeatable `--profile-directory` add profile resources
  while retaining the primary CF registry and default profile;
- `data_directory` is a complete, replaceable offline data root containing a
  CF registry, profile defaults, and profiles, useful for testing and controlled
  installations.

An installable example plugin is intentionally deferred until entry-point
discovery is implemented. Publishing one in version 0.1 would imply a packaging
and registration API that cannot yet be executed. The field-level profile
format is stable preparation for that work; the next version should add entry-
point discovery, its compatibility policy, and a tested example package
together.

## Public selection

Python:

```python
import cfregions

profile = cfregions.get_spatial_profile(
    profile="cfregions-default",
    profile_version="2026.09.1",
)
profile_ids = cfregions.list_spatial_profile_ids()
profile_versions = cfregions.list_spatial_profile_versions(profile=profile.id)
additional_profiles = cfregions.list_spatial_profiles(
    profile_directories=["/path/to/additional-profiles"]
)
matches = cfregions.match_regions(
    lonlat="7.990654, 24.602804",
    cf_version="5",
    profile=profile.id,
    profile_version=profile.version,
)
```

CLI:

```console
cfregions profiles
cfregions profiles --profile-directory /path/to/additional-profiles
cfregions lookup --lonlat "7.990654, 24.602804" \
  --cf-version 5 \
  --profile cfregions-default \
  --profile-version 2026.09.1
```

Aliases are convenient interactively. Reproducible workflows should retain
the resolved CF version, profile ID/version, and any checksums returned by
`get_dataset_info()` or structured CLI output.

## Rules for future contributed profiles

A contributed profile should:

- provide a geometry for every name in each declared supported CF version;
- declare deterministic and core-supported lookup behavior;
- use `OGC:CRS84` unless the core explicitly supports another CRS;
- provide feature-level geometry sources, versions, licenses, and methods;
- provide every hierarchy edge explicitly with its own provenance;
- include exact input and output hashes when reproducible publication or
  integrity verification requires them;
- document intended use, scale, uncertainty, gaps, overlaps, and exclusions;
- issue a new immutable profile version for any result-changing correction.

Patch overlays and silent inheritance are outside the initial contract because
they obscure provenance. Semantic alternatives, such as area and diagnostic-
section interpretations, should be separate profiles rather than geometry
resolutions. Profile packages should remain data-oriented; arbitrary custom
matching code would require a separate, explicitly versioned extension
contract.
