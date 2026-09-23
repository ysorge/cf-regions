"""Support ``python -m cfregions`` as an alternative CLI entry point."""

from .cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
