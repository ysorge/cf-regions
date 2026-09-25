# Changelog

All notable changes to `cf-regions` are documented here. The project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.1.0

This is the first public release.

### Added

- Version-aware access to CF Standardized Region Lists 1 through 5.
- Offline coordinate lookup, hierarchy traversal, region metadata, interpreted
  GeoJSON geometry, and detailed mapping provenance.
- Typed Python API and shell-friendly CLI with separate names, table, JSON, and
  JSONL output formats.
- Declarative, versioned spatial-interpretation profiles with optional file
  integrity checksums, additive external profile directories, and discovery
  APIs.
- Low- and high-detail shapes plus GeoJSON, WKT, WKB, and WKB-hex exports.
- High-detail coordinate lookup with an optional generated spatial index and
  lazy geometry decoding; plain GeoJSON profiles remain fully supported.
- Reproducible dataset tooling, JSON Schemas, tests, type checks, and packaging
  validation.

### Documentation

- Document data sources, mapping behavior, known limitations, profile authoring,
  and the maintenance workflow.
- Keep the README focused on installation and first use, with detailed Python
  API and command-line guides under `docs/`.
