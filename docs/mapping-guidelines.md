# Mapping Guidelines for `cf-regions`

## Purpose

`cf-regions` connects names from the CF Standardized Region List with explicit spatial interpretations that can be used for coordinate lookup and visualization.

The central design rule is:

> CF defines the semantic region name; `cf-regions` provides an explicit, versioned spatial interpretation of that region.

The CF region concept and a geometry used to represent it are therefore related,
but they are not the same object.

## 1. Do not present a mapping geometry as the authoritative CF geometry

The CF Standardized Region List defines controlled names, not canonical spatial
boundaries or transects. A geometry for `atlantic_ocean`, `denmark_strait`, or
any other CF region is a mapping supplied by a particular dataset and method.

Consequently:

- Do not describe a polygon or line as *the* geometry of a CF region.
- Describe it as a spatial representation or interpretation used by a named mapping dataset.
- Keep the CF vocabulary version separate from the mapping-dataset version.
- Allow for multiple legitimate spatial interpretations of the same CF region.

## 2. Keep semantic identity and spatial representation separate

The data model should distinguish at least:

```text
CF region concept
    name: denmark_strait
    vocabulary: CF Standardized Region List
    vocabulary version: ...

Spatial representation
    geometry: Polygon / MultiPolygon / LineString / ...
    mapping dataset: ...
    mapping version: ...
    source: ...
    method: ...
```

A CF region may in principle have no available geometry, one geometry, or multiple representations from different sources, resolutions, or methods. A published mapping profile must declare its coverage policy. The currently bundled `cf-regions` profile deliberately requires one representation for every name in its supported CF release; partial profiles remain a future extension.

Geometry type is also part of the spatial interpretation, not an intrinsic
property of a CF name. A strait or channel may be represented as an area in one
mapping and as a diagnostic transport section in another. The selected type
must follow a documented scientific use and source, be exposed in metadata, and
must not be inferred only from words such as `strait`, `channel`, or `passage`.
Fields such as `kind` or `geometry_type` must be documented as mapping metadata,
not presented as assertions made by the CF vocabulary.

## 3. Treat lookup and geometry retrieval as distinct operations

These operations serve different purposes:

```text
coordinate or geometry -> matching CF region concept(s)
CF region concept      -> spatial representation(s)
```

They are not guaranteed to be mathematical inverses. A region may have multiple representations, and lookup behavior may depend on the selected mapping dataset and spatial predicate.

The current API exposes the resolved mapping on every result and allows rendering detail to be selected independently:

```python
matches = cfregions.match_regions(
    longitude=-27.0,
    latitude=66.0,
)
print(matches[0].mapping.id, matches[0].mapping.version)

feature = cfregions.get_region_shape(
    region_name="north_sea",
    geometry_resolution="high",
)
```

The bundled registry currently has one spatial interpretation profile. Profile
identity and version are explicit API and CLI selections, never values
overloaded onto `geometry_resolution`: resolution changes detail within one
interpretation, while a different profile may change interpreted extent,
geometry role, hierarchy, or lookup behavior. The provider contract and future
contribution rules are documented in [Spatial interpretation
profiles](spatial-interpretation-profiles.md).

## 4. Return structured mapping results

A lookup result should not be only a region-name string. It should contain enough information to explain and reproduce the match.

At minimum, expose:

- the matched CF region name;
- the spatial relation or predicate used;
- the mapping dataset and version;
- the source of the mapping geometry;
- the lookup method;
- the CF vocabulary version, where relevant.

For example:

```python
match.region.name        # "denmark_strait"
match.relation           # "covered_by"
match.predicate          # "covers" (boundary inclusive)
match.mapping.id         # "cfregions-default"
match.mapping.version    # "2026.09.1"
match.method             # "polygon_lookup"
match.source.uri         # source URI (with name/version/license alongside it)
```

Do not invent a numerical confidence score unless it has a defined and defensible meaning.

Hierarchy expansion must remain distinguishable from geometric matching. A
hierarchy edge should identify its child, parent, source, derivation method, and
mapping version. An edge may be attributed to GCMD only when the retained GCMD
path evidences that relationship; composite, global, or diagnostic-section
connections must be labelled as mapping curation. Since a region may have more
than one parent, hierarchy interfaces must model a directed acyclic graph rather
than assume a strict tree.

## 5. Support zero, one, or multiple matches

A lookup must not assume that every position belongs to exactly one CF region.

Valid outcomes include:

- no matching region;
- exactly one matching region;
- multiple matching regions because representations overlap or are nested;
- multiple matches produced by different mapping datasets.

The normal return type should therefore be a collection of matches, even when one match is common.

Do not silently discard additional matches. If the library offers a single-result convenience function, it must use a documented selection policy and must raise or otherwise signal unresolved ambiguity.

## 6. Make ambiguity visible and selection rules explicit

When more than one match is valid, the software should either:

1. return all matches; or
2. apply an explicitly requested, documented selection policy.

Possible policies might include:

- prefer the most specific region;
- prefer a named mapping dataset;
- prefer a particular mapping version;
- return only matches at a requested hierarchy level.

Never rely on polygon order, file order, index order, or plugin discovery order to resolve ambiguity.

## 7. Define boundary semantics deliberately

Points on polygon boundaries require stable behavior. The result must not depend on an accidental choice of geometry-library function.

The implementation must document:

- which spatial predicate is used for point lookup;
- whether boundary points count as matches;
- how shared boundaries are handled;
- how numerical precision and coordinate tolerance are handled, if applicable.

For inclusive point-in-region lookup, a predicate equivalent to `covers` / `covered_by` is usually more appropriate than strict `contains` / `within`, because it includes boundary points. This choice should be explicit and covered by tests.

If a point lies on a boundary shared by two region polygons, returning both regions is preferable to selecting one arbitrarily.

## 8. Make coordinates and CRS unambiguous

Public APIs should avoid unlabelled coordinate tuples.

Prefer explicit arguments in longitude/latitude order, matching GeoJSON and the CLI:

```python
cfregions.match_regions(longitude=-27.0, latitude=66.0)
```

Explicitly named combined forms such as `lonlat=(-27.0, 66.0)` and
`latlon=(66.0, -27.0)` are also unambiguous. An API may support them for easy
clipboard and command-line interchange, provided it rejects mixed coordinate
forms instead of guessing the intended order.

If positional coordinates or general geometries are accepted, document:

- coordinate order;
- required or assumed CRS;
- accepted geometry types;
- transformation behavior;
- error behavior for missing or unsupported CRS information.

Defaults must be explicit. Do not silently reinterpret coordinates in an unknown CRS.

## 9. Preserve provenance

Every spatial representation should carry sufficient provenance to answer:

- Who or what produced it?
- Which source data were used?
- Which source-data version or release was used?
- Which transformation or derivation method was applied?
- Which license and citation apply?
- When was the artifact generated?

A lightweight metadata model is sufficient initially, but provenance must not be reduced to an undocumented filename or package version.

Recommended fields include:

```text
mapping_id
mapping_version
profile_id
profile_version
source_id
source_version
source_uri
citation
license
method
created_at
```

Package version, CF vocabulary version, mapping version, and upstream source version are separate concepts and should not be conflated.

## 10. Make mappings deterministic and versioned

Given the same:

- input coordinate or geometry;
- CRS;
- mapping dataset and version;
- lookup configuration;
- library behavior version;

the result should be deterministic.

Changes to geometries, simplification, hierarchy, predicates, or conflict-resolution rules may change results and must not be introduced silently under the same mapping version.

Mapping artifacts should therefore be immutable once released, or at least content-addressed and reproducibly generated. A newer mapping should receive a new version.

## 11. Separate vocabulary updates from mapping updates

A new CF Standardized Region List version and a new spatial mapping release are independent events.

For example:

- the CF list may add or rename a region while the polygons remain unchanged;
- a polygon source may improve while the CF vocabulary remains unchanged;
- a mapping release may add coverage for existing CF names;
- a mapping may intentionally support only a declared subset of a CF vocabulary version.

Compatibility metadata should state which CF vocabulary version or range a mapping targets and which region names it covers.

## 12. Model hierarchy separately from geometry

Semantic relationships such as `broader`, `narrower`, or `part_of` must not be inferred solely from polygon containment unless that derivation is explicitly part of the mapping methodology.

Likewise, geometric containment does not automatically establish an authoritative semantic hierarchy.

If hierarchy is provided, record whether it comes from:

- an authoritative vocabulary source;
- the mapping dataset;
- an algorithmic derivation;
- a project-specific curation decision.

Hierarchy expansion must remain visibly distinct from a spatial match. In `cf-regions`, `relation="ancestor"`, `method="hierarchy_expansion"`, and `predicate="broader"` mean that the returned name is semantically connected to a direct result. They do **not** assert that the queried point was tested against, or lies within, the ancestor's geometry.

## 13. Avoid hidden fallbacks

The library should not silently:

- switch to another mapping dataset when a requested one is unavailable;
- substitute a newer mapping version;
- drop unsupported CF region names;
- transform an unknown CRS as if it were longitude/latitude;
- choose the first of several matches;
- repair invalid geometry without reporting it.

Fallbacks may be offered, but they must be documented and visible in the result metadata or warnings.

## 14. Validate mapping datasets before release

Each mapping release should be validated for at least:

- valid geometry;
- declared CRS and coordinate order;
- stable unique identifiers;
- references only to supported CF region names;
- duplicate or missing region assignments;
- unexpected overlaps and gaps;
- empty geometries;
- reproducible generation;
- complete source, license, and version metadata.

Overlaps and gaps are not necessarily errors, but they must be identified and understood rather than accidentally introduced.

For example, the bundled mapping retains the pinned SeaVoX definitions of the North Sea and Baltic Sea. Those source geometries do not meet. `cf-regions` must document that gap and its provenance rather than drawing a project-specific connector that could be mistaken for an upstream or CF boundary.

## 15. Test behavior, not only data loading

The test suite for currently supported behavior should include:

- a point clearly inside a region;
- a point on an outer boundary;
- a point on a shared boundary;
- overlapping or nested regions;
- declared dataset CRS and longitude/latitude order;
- longitude/latitude order checks;
- deterministic repeat lookup;
- exact mapping-version identity in results;
- serialization and round-trip preservation of provenance;
- compatibility between declared CF and mapping versions.

A point outside all mapped regions is not possible in the bundled complete profile because `global` covers the declared world extent. It should be tested when partial mapping profiles are supported. Likewise, missing representations and competing scientific mappings belong in the tests when those features are introduced; low/high detail variants of the same interpretation are not competing mappings.

Regression fixtures should pin both expected region matches and the exact mapping version used.

## 16. Keep the initial API simple without erasing necessary semantics

A small first release is desirable. It may initially ship with one spatial
interpretation profile and one lookup method. Even then, the API and result
model should preserve:

- the identity of that profile and its mapping;
- its version and provenance;
- collection-based lookup results;
- explicit boundary behavior;
- a future path to contributed profiles and multiple representations.

The implementation does not need premature machinery for every possible data source. It does need to avoid interfaces that falsely imply one canonical polygon or exactly one possible match.

## Developer checklist

Before merging mapping-related work, confirm:

- [ ] CF concepts and mapping geometries are separate in the model.
- [ ] Every result identifies its mapping dataset and version.
- [ ] Lookup can return zero, one, or multiple matches.
- [ ] Ambiguity is not resolved by incidental ordering.
- [ ] Boundary behavior is documented and tested.
- [ ] Coordinate order and CRS requirements are explicit.
- [ ] Provenance, source, citation, and license metadata are preserved.
- [ ] Vocabulary and mapping versions are tracked independently.
- [ ] Mapping changes that affect results require a new mapping version.
- [ ] Hidden fallbacks are avoided or surfaced clearly.
- [ ] Dataset validation covers invalid geometries, overlaps, gaps, and coverage.
- [ ] Regression tests pin mapping versions and edge-case behavior.

## Summary

The mapping layer in `cf-regions` should be explicit, versioned, provenance-aware, deterministic, and capable of representing ambiguity. It should never imply that its polygons are authoritative CF boundaries. Its responsibility is to provide reproducible spatial interpretations of CF region concepts and to make every assumption behind those interpretations visible to users and developers.
