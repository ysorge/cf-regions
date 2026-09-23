# Contributing

Contributions are welcome through GitHub issues and pull requests. Please open
an issue before substantial features, public API changes, or new spatial
interpretations so the approach and scope can be discussed. Small fixes and
documentation improvements may be submitted directly.

Participation is governed by the [Code of conduct](CODE_OF_CONDUCT.md).

## Development setup

Use one of the latest Python versions in a virtual environment:

```console
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

On Windows, use `.venv\Scripts\python` instead. Before opening a pull 
request, run:

```console
ruff check src tests tools
mypy src
pytest --cov=cfregions --cov-report=term-missing
python -m build
twine check dist/*
```

Keep the core free of web and GUI dependencies. Public API changes need tests
and a changelog entry. Prefer small, typed functions and preserve separation
between data loading, indexed domain logic, the Python API, and the CLI.

## Vocabulary, geometry, and hierarchy changes

CF supplies standardized names, not official boundaries. Spatial-interpretation
changes must include a stable source and compatible license, a pinned version,
a reproducible derivation method, updated attribution and checksums, relevant
tests, and documented limitations.

Follow the [dataset maintenance workflow](docs/dataset-maintenance.md). Source
roles are documented in [Data sources and mapping method](docs/data-sources-and-mapping.md),
and normative design decisions are in the [mapping guidelines](docs/mapping-guidelines.md).
Run `python tools/build_dataset.py --help` for builder inputs. Runtime lookup
must remain fully offline.

By contributing, you agree that your code contribution is distributed under
Apache-2.0. Do not submit data or other material that cannot be redistributed
under the terms documented in `DATA_LICENSES.md`.
