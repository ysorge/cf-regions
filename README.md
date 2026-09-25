# cf-regions

[![Available on pypi](https://img.shields.io/pypi/v/cf-regions.svg)](https://pypi.python.org/pypi/cf-regions/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
 [![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![CI - Test](https://github.com/ysorge/cf-regions/actions/workflows/ci.yml/badge.svg)](https://github.com/ysorge/cf-regions/actions/workflows/ci.yml)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22959858.svg)](https://doi.org/10.5281/zenodo.22959858)

Experimental Python library for mapping and lookup of [CF Standardized Region List][cf-list] names to geometries and region hierarchy. The CF Standardized Region List is a controlled vocabulary of region names for Earth science data. It is part of the [CF Conventions](https://cfconventions.org/) and based on the NASA GCMD keyword list for locations.

> [!IMPORTANT]
> CF standardizes region names, not boundaries. The bundled shapes in `cf-regions` are a
> spatial interpretation for experimental discovery and categorization. They are
> not official CF boundaries and must not be used for navigation or legal decisions.

> [!NOTE]
> **Project status: alpha.** The public API is typed and tested, but may still
> change while the project matures.

## Features

- Offline coordinate-to-region lookup
- CF Standardized Region Lists 1 through 5
- Simple name results or detailed, provenance-rich matches
- Region metadata, hierarchy, and low/high-detail GeoJSON shapes
- Versioned spatial interpretation profiles
- A typed Python API and shell-friendly CLI

The package includes all required vocabulary and geometry resources and does
not download data during lookup.

## Installation

Install from PyPI:

```console
python -m pip install cf-regions
```

To work on the current source checkout instead:

```console
git clone https://github.com/ysorge/cf-regions.git
cd cf-regions
python -m pip install -e ".[dev]"
```

## Quick start

For a simple lookup of region names covering a coordinate, run:

```console
cfregions lookup --lonlat "-90.0, 25.0"
```

In Python:

```python
import cfregions
names = cfregions.match_region_names(longitude=-90.0, latitude=25.0)
names
```

## Understanding the results

A point can match several valid regions. Direct geometry matches, proximity to
diagnostic sections, and semantic hierarchy ancestors are kept distinguishable
in detailed results. The selected CF vocabulary version and spatial
interpretation profile are independent and are both included in provenance.

For the scientific meaning of the mapping, its upstream sources, and known
limitations, read [Data sources and mapping method][data-sources]. The
[Mapping guidelines][mapping-guidelines] explain why these shapes are explicit,
versioned interpretations rather than official CF boundaries.

## Spatial interpretation profiles

`cf-regions` uses spatial interpretation profiles to map CF region names to geometries and region hierarchy. This allows the same CF vocabulary to be interpreted differently for different scientific purposes or domains, while retaining the same stable region names and descriptions. Each profile is self-contained and immutable, with its own declared geometry sources, hierarchy, and lookup semantics. The built-in default profile is `cfregions-default`. It is the only profile bundled with the package.

## Documentation

- [API usage][api-usage] — lookups, functions, return values, profiles,
  geometry, hierarchy, and errors
- [CLI usage][cli-usage] — commands, formats, pipelines, and exports
- [Data sources and mapping method][data-sources] — how matches are produced
- [Spatial interpretation profiles][spatial-profiles] — profile architecture
  and extension model
- [Spatial profile file format][profile-format] — authoring profile data
- [Mapping guidelines][mapping-guidelines] — design and scientific rules
- [Dataset maintenance][dataset-maintenance] — updating bundled CF and mapping
  data
- [Data licenses][data-licenses] — source terms and attribution

## Development and support

For a development checkout:

```console
git clone https://github.com/ysorge/cf-regions.git
cd cf-regions
python -m pip install -e ".[dev]"
pytest
```

Report bugs and request features through [GitHub Issues][issues]. Report
security vulnerabilities privately as described in the [security
policy][security].

## Contributing

Contributions are welcome through issues and pull requests. Please open an
issue first for substantial features, API changes, or new spatial
interpretations. Small fixes and documentation improvements may be submitted
directly. See the [contribution guide][contributing] and
[Code of conduct][code-of-conduct].

## Authors and maintainership

`cf-regions` was initiated and originally developed by
[Yves Sorge](https://github.com/ysorge) during the
[CF Conventions Community Workshop 2026][workshop] at ECMWF in Bonn, Germany.
The project is currently maintained by its original author.

Additional contributors are recorded in
[AUTHORS.md](https://github.com/ysorge/cf-regions/blob/main/AUTHORS.md) and the
repository history. Maintainer responsibility may move to another person or
organization without replacing the authorship of existing contributions.

## License

The `cf-regions` source code is licensed under the [Apache License
2.0][license] (`Apache-2.0`). Bundled data retains the separate terms documented
in [Data licenses][data-licenses]. Downstream users must preserve applicable
source notices and attributions.

[api-usage]: https://github.com/ysorge/cf-regions/blob/main/docs/api-usage.md
[cf-list]: https://cfconventions.org/Data/standardized-region-list/standardized-region-list.current.html
[cli-usage]: https://github.com/ysorge/cf-regions/blob/main/docs/cli-usage.md
[code-of-conduct]: https://github.com/ysorge/cf-regions/blob/main/CODE_OF_CONDUCT.md
[contributing]: https://github.com/ysorge/cf-regions/blob/main/CONTRIBUTING.md
[data-licenses]: https://github.com/ysorge/cf-regions/blob/main/DATA_LICENSES.md
[data-sources]: https://github.com/ysorge/cf-regions/blob/main/docs/data-sources-and-mapping.md
[dataset-maintenance]: https://github.com/ysorge/cf-regions/blob/main/docs/dataset-maintenance.md
[issues]: https://github.com/ysorge/cf-regions/issues
[license]: https://github.com/ysorge/cf-regions/blob/main/LICENSE
[mapping-guidelines]: https://github.com/ysorge/cf-regions/blob/main/docs/mapping-guidelines.md
[profile-format]: https://github.com/ysorge/cf-regions/blob/main/docs/profile-format.md
[security]: https://github.com/ysorge/cf-regions/blob/main/SECURITY.md
[shapely]: https://shapely.readthedocs.io/
[spatial-profiles]: https://github.com/ysorge/cf-regions/blob/main/docs/spatial-interpretation-profiles.md
[workshop]: https://cfconventions.org/Meetings/2026-Workshop.html
