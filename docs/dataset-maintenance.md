# Dataset maintenance

## Purpose

This document is the operational workflow for maintaining the data distributed
with `cf-regions`. It covers new CF Standardized Region List releases, upstream
geometry or hierarchy updates, and corrections to the project mapping.

Read [Data sources and mapping method](data-sources-and-mapping.md) before
changing data, [Mapping guidelines](mapping-guidelines.md) for normative design
rules, and [Data licenses and attribution](../DATA_LICENSES.md) before adding or
updating a source.

## Release policy

Published artifacts are immutable. Never replace data under an existing profile
version or silently change its lookup behavior.

Keep these changes independent:

- A new CF vocabulary receives a new CF version manifest.
- A geometry, hierarchy, processing, or lookup-behavior change receives a new
  spatial profile version and profile directory.
- A package release declares which CF and profile versions it bundles.

The CF registry and spatial-profile provider are independent selections. Exact
reproduction requires recording the
resolved profile ID/version, CF version, lookup behavior version, and geometry
hash. Do not overload geometry resolution or silently replace the default
profile.

## Routine upstream review

A lightweight quarterly check and a human review at least annually are
sufficient for the current sources. A new upstream release is a review trigger,
not an automatic mapping update.

| Source | Check | Update only when |
| --- | --- | --- |
| CF Standardized Region List | Current version, identifiers, descriptions | CF publishes a new release |
| NASA GCMD Location Keywords | Diff retained paths for CF names | A relevant Location path changes or a correction is accepted |
| SeaVoX | Product version and selected MRGIDs | Relevant shapes or identifiers change and the new interpretation is accepted |
| Natural Earth | Used layer versions and relevant feature changes | A correction or improvement materially affects a mapped region |
| OMIP/CMIP tables | Referenced definitions and successor protocols | The project deliberately adopts a new scientific definition |
| Project mapping | Issue reports, known gaps/overlaps, methods | A documented correction or new interpretation is approved |

Record the review even when it results in no update. Do not fetch mutable
upstream data during runtime lookup or during an ordinary package build.

## Adding a CF Standardized Region List release

### 1. Acquire and verify the vocabulary

1. Obtain the numbered XML release from the official CF vocabulary site. Do not
   use the mutable `current` URL as the retained artifact.
2. Save it as
   `src/cfregions/data/vocabularies/standardized-region-list.<version>.xml`.
3. Verify its embedded `version_number`, publication `date`, entry identifiers,
   descriptions, and SHA-256 digest.
4. Diff identifiers and descriptions against the previously current release.
   Classify additions, removals, aliases or renames, and description-only
   changes.
5. Confirm the applicable license and update attribution if it changed.

Do not edit the upstream XML to make it fit the mapping. Any normalization must
be explicit in code or metadata while the retained vocabulary remains exact.

### 2. Assess profile compatibility

For every identifier in the new vocabulary, answer:

- Does the current geometry edition already contain a feature with this exact
  name?
- Is the existing spatial interpretation still appropriate?
- Is an area or diagnostic section intended, and which scientific usage and
  source justify that geometry type?
- Does it have complete source, method, version, license, and hierarchy data?
- Do existing parents still refer to names present in the new vocabulary?

If every new-release name is already covered and no spatial interpretation must
change, add the CF version to `supported_cf_versions` in the existing profile
manifest. This is how one profile version can support several CF vocabularies;
the runtime loader filters its complete geometry and hierarchy to the selected
vocabulary.

If any name lacks geometry, or if geometry, hierarchy, lookup behavior, or
processing must change, create a new profile edition as described below. The
bundled complete profile does not silently omit unsupported names.

### 3. Create the CF version manifest

Add `src/cfregions/data/versions/<version>.json` containing:

- a stable, CF-only `dataset_id`;
- the exact region count;
- CF version, date, numbered source URL, vocabulary path, and SHA-256.

The CF version manifest must not point to a geometry or profile. Profile
compatibility is declared in the profile manifest instead.

Register the new file in `src/cfregions/data/catalog.json`. Change
`default_version` and the `current` alias only after all review and validation
has passed. Historical catalog entries and vocabulary files must remain
available.

### 4. Add regression coverage

At minimum, test:

- discovery through `list_cf_versions()` and `cfregions versions`;
- exact name count and representative added or removed identifiers;
- dataset-info version, date, URL, and vocabulary hash;
- geometry coverage for every name;
- lookup and shape retrieval for newly added concepts;
- hierarchy edges for new or changed relationships;
- continued loading of all historical CF releases.

## Creating a new profile edition

Use a new immutable edition directory such as
`src/cfregions/data/profiles/<profile-id>/<profile-version>/`. Keep its
`manifest.json`, `hierarchy.json`, and `geometry/` representations together.
Never regenerate files in a published edition under the same version.

No profile index needs updating: the new `manifest.json` is auto-discovered.
Its `profile.id` and `profile.version` are authoritative; the enclosing
directory names are only the recommended organization. Update
`profile-settings.json` only when intentionally changing the global built-in
default. See [Spatial interpretation profiles](spatial-interpretation-profiles.md)
before introducing another profile identity. The profile does not contain a
copy of the CF catalog, version manifests, or vocabulary XML.

### 1. Pin inputs and decisions

Before running the builder:

1. Record stable upstream versions, URLs or DOIs, licenses, and expected
   attribution.
2. Retain local input filenames that identify their release.
3. Review selectors such as SeaVoX MRGIDs and Natural Earth feature names.
4. Update project mapping rules for every added or changed CF name:
   geometry construction, source metadata, hierarchy edges, NVS concept link, kind,
   contexts, and specificity.
5. Update the builder's expected CF count, source/version constants, pinned
   Natural Earth versions, resolution profiles, mapping version, hierarchy
   version/date, and documented limitations.
6. Add or update tests for source loaders and affected geographical behavior.

The builder currently targets the complete bundled profile and intentionally
contains explicit selections. A new CF name therefore requires a deliberate
implementation; changing only the expected count is insufficient.

### 2. Build both representations

Install the core development dependencies, then inspect the exact command-line
inputs:

```console
python tools/build_dataset.py --help
```

Run the builder first for `low` and then for `high`, using the same pinned input
set and the same new output directory. The final manifest must declare both
representations and their processing parameters and SHA-256 hashes. When a
high representation exists, the builder also derives its optional WKB pack and
small lookup index; these are runtime accelerators and must always be
re-generated from the authoritative GeoJSON rather than edited. It also emits
a separate, checksummed `hierarchy.json`. The builder
must complete with exact CF-name parity; do not bypass a missing-name or source
version assertion.

The build tool performs no upstream downloads. Store acquisition notes outside
the runtime package when upstream redistribution rules do not permit retaining
raw source files in the repository.

### 3. Review the generated mapping

Review both machine validity and scientific behavior:

- exact feature count and unique identifiers;
- valid, non-empty Polygon/MultiPolygon or LineString/MultiLineString geometry;
- `OGC:CRS84` longitude/latitude order;
- source, version, URI, license, method, and contexts for every feature;
- low/high interpretation equivalence;
- expected overlaps, shared boundaries, and gaps;
- points inside affected regions and on important boundaries;
- antimeridian and polar behavior where relevant;
- hierarchy acyclicity and per-edge GCMD/curation provenance;
- deterministic rebuild from the same inputs.

Inspect generated provenance through both API and CLI rather than only viewing
the map. A visually plausible shape can still have the wrong name, source,
coordinate order, hierarchy, or lookup behavior.

### 4. Connect and document the edition

Declare compatible CF versions in the new profile manifest. Auto-discovery
requires no registration entry. Do not modify CF version manifests to point at
a profile. Update:

- the changelog with source and behavioral differences;
- `DATA_LICENSES.md` when legal terms, citations, or required notices change;
- [Data sources and mapping method](data-sources-and-mapping.md) when a source's
  role or the lookup algorithm changes;
- mapping limitations and user-facing provenance text;
- regression expectations that intentionally changed.

Do not describe an upstream source refresh as inherently more correct. State
what changed and why this project adopted it.

## Validation before release

Run the complete project checks:

```console
ruff check src tests tools
mypy src
pytest --cov=cfregions --cov-report=term-missing
python -m build
twine check dist/*
```

Also test a built `cf-regions` wheel in a clean environment so validation does
not accidentally depend on the repository's `tools/` package or raw inputs.

Before publishing, confirm:

- [ ] the numbered CF XML is exact and checksummed;
- [ ] the CF and profile versions are independent and correct;
- [ ] `current` advances only intentionally;
- [ ] old CF releases still load;
- [ ] every supported name has one bundled representation;
- [ ] lookup remains pinned to the declared resolution;
- [ ] source and hierarchy provenance is complete;
- [ ] known ambiguity, overlaps, and gaps are documented;
- [ ] licenses, citations, and notices are current;
- [ ] package artifacts contain every declared manifest and geometry resource;
- [ ] any declared lookup artifact was regenerated and matches its GeoJSON source;
- [ ] release notes identify any result-changing behavior.

## Corrections after publication

Do not overwrite an already published vocabulary, geometry, or manifest. For a
profile-data correction, create a new profile edition and package release. For
an implementation-only defect that leaves the data unchanged, retain the
profile version and change only the package version. If lookup semantics or
geometry-derived results change, advance the profile or behavior version as
appropriate and describe the migration.
