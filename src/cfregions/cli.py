"""Command-line interface for :mod:`cfregions`."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypedDict

from shapely.geometry import shape as shapely_shape

from . import __version__
from .api import (
    get_dataset_info,
    get_region_shape,
    list_cf_versions,
    list_hierarchy_edges,
    list_regions,
    list_spatial_profiles,
    match_regions,
)
from .catalog import resolve_coordinates
from .errors import CFRegionsError
from .models import HierarchyEdge


class _DatasetOptions(TypedDict):
    cf_version: str
    profile: str
    profile_version: str
    data_directory: Path | None
    profile_directories: tuple[Path, ...]


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _json_lines(values: Sequence[object]) -> str:
    if not values:
        return ""
    return "\n".join(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")) for value in values
    ) + "\n"


def _lines(values: Sequence[str]) -> str:
    return "\n".join(values) + ("\n" if values else "")


def _table(headers: tuple[str, ...], rows: Sequence[tuple[str, ...]]) -> str:
    if not rows:
        return "No matches.\n"
    widths = tuple(
        max(len(header), *(len(row[index]) for row in rows))
        for index, header in enumerate(headers)
    )

    def formatted_row(row: tuple[str, ...]) -> str:
        return "  ".join(
            value.ljust(widths[index]) for index, value in enumerate(row)
        ).rstrip()

    separator = tuple("-" * width for width in widths)
    return _lines(
        [
            formatted_row(headers),
            formatted_row(separator),
            *(formatted_row(row) for row in rows),
        ]
    )


def _edge_label(edge: HierarchyEdge) -> str:
    return "GCMD" if edge.origin == "gcmd_path_projection" else "curated"


def _hierarchy_tree(
    region_names: Sequence[str],
    edges: Sequence[HierarchyEdge],
    *,
    selected_region: str | None,
) -> str:
    lines: list[str] = []
    seen: set[str] = set()

    if selected_region is not None:
        parents_by_child: dict[str, list[HierarchyEdge]] = {}
        for edge in edges:
            parents_by_child.setdefault(edge.child, []).append(edge)

        def visit_parents(name: str, prefix: str) -> None:
            parents = sorted(
                parents_by_child.get(name, ()), key=lambda edge: edge.parent
            )
            for index, edge in enumerate(parents):
                is_last = index == len(parents) - 1
                connector = "`-- " if is_last else "|-- "
                repeated = edge.parent in seen
                suffix = " (see above)" if repeated else ""
                lines.append(
                    f"{prefix}{connector}{edge.parent} [{_edge_label(edge)}]{suffix}"
                )
                if not repeated:
                    seen.add(edge.parent)
                    visit_parents(edge.parent, prefix + ("    " if is_last else "|   "))

        lines.append(selected_region)
        seen.add(selected_region)
        visit_parents(selected_region, "")
        return _lines(lines)

    children_by_parent: dict[str, list[HierarchyEdge]] = {}
    child_names = set()
    for edge in edges:
        children_by_parent.setdefault(edge.parent, []).append(edge)
        child_names.add(edge.child)
    roots = sorted(set(region_names) - child_names)

    def visit_children(name: str, prefix: str) -> None:
        children = sorted(
            children_by_parent.get(name, ()), key=lambda edge: edge.child
        )
        for index, edge in enumerate(children):
            is_last = index == len(children) - 1
            connector = "`-- " if is_last else "|-- "
            repeated = edge.child in seen
            suffix = " (see above)" if repeated else ""
            lines.append(
                f"{prefix}{connector}{edge.child} [{_edge_label(edge)}]{suffix}"
            )
            if not repeated:
                seen.add(edge.child)
                visit_children(edge.child, prefix + ("    " if is_last else "|   "))

    for root_index, root in enumerate(roots):
        if root_index:
            lines.append("")
        lines.append(root)
        seen.add(root)
        visit_children(root, "")
    return _lines(lines)


def _add_data_directory_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--data-directory",
        type=Path,
        help="external self-describing CF and profile data root",
    )


def _add_profile_directory_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--profile-directory",
        type=Path,
        action="append",
        default=[],
        help="add profiles discovered below this directory (repeatable)",
    )


def _add_dataset_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cf-version",
        default="current",
        help="CF Standardized Region List version (default: current)",
    )
    parser.add_argument(
        "--profile",
        default="default",
        help="spatial interpretation profile ID or alias (default: default)",
    )
    parser.add_argument(
        "--profile-version",
        default="current",
        help="spatial interpretation profile version or alias (default: current)",
    )
    _add_data_directory_argument(parser)
    _add_profile_directory_argument(parser)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cfregions",
        description="Look up CF standardized geographic regions.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    lookup = subparsers.add_parser(
        "lookup", help="find all region names connected to a WGS84 point"
    )
    _add_dataset_arguments(lookup)
    lookup.add_argument("--longitude", type=float, help="longitude in degrees")
    lookup.add_argument("--latitude", type=float, help="latitude in degrees")
    lookup.add_argument(
        "--lonlat",
        metavar="LONGITUDE,LATITUDE",
        help="comma-separated longitude and latitude",
    )
    lookup.add_argument(
        "--latlon",
        metavar="LATITUDE,LONGITUDE",
        help="comma-separated latitude and longitude",
    )
    lookup.add_argument(
        "--section-tolerance-km",
        type=float,
        default=0.0,
        help="also match section lines within this distance (default: 0)",
    )
    lookup.add_argument(
        "--ancestors",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="include semantic hierarchy ancestors (default: enabled)",
    )
    lookup.add_argument(
        "--format",
        choices=("names", "table", "json", "jsonl"),
        default="names",
        help="names, human-readable table, full JSON, or one JSON match per line (default: names)",
    )

    regions = subparsers.add_parser("regions", help="list standardized region names")
    _add_dataset_arguments(regions)
    regions.add_argument(
        "--format",
        choices=("names", "table", "json", "jsonl"),
        default="names",
        help=(
            "names, human-readable table, JSON array, or one JSON region per line "
            "(default: names)"
        ),
    )

    hierarchy = subparsers.add_parser(
        "hierarchy", help="show the GCMD-derived and curated mapping hierarchy"
    )
    _add_dataset_arguments(hierarchy)
    hierarchy.add_argument(
        "region_name",
        nargs="?",
        help="optional region whose ancestor subgraph is shown",
    )
    hierarchy.add_argument(
        "--format",
        choices=("tree", "table", "json", "jsonl"),
        default="tree",
        help="tree, edge table, graph JSON, or one JSON edge per line (default: tree)",
    )

    shape = subparsers.add_parser(
        "shape", help="export one interpreted region geometry"
    )
    _add_dataset_arguments(shape)
    shape.add_argument("region_name", help="exact CF standardized region name")
    shape.add_argument(
        "--geometry-resolution",
        help="declared rendering resolution (default: mapping default)",
    )
    shape.add_argument(
        "--format",
        choices=("geojson", "wkt", "wkb", "wkb-hex"),
        default="geojson",
        help="geospatial output format (default: geojson)",
    )
    shape.add_argument("--output", type=Path, help="output file (default: stdout)")

    info = subparsers.add_parser("info", help="show dataset version and provenance")
    _add_dataset_arguments(info)
    info.add_argument(
        "--format", choices=("text", "json"), default="text", help="output format"
    )

    versions = subparsers.add_parser("versions", help="list available CF releases")
    _add_data_directory_argument(versions)

    profiles = subparsers.add_parser(
        "profiles", help="list available spatial interpretation profiles"
    )
    _add_data_directory_argument(profiles)
    _add_profile_directory_argument(profiles)
    profiles.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="output format (default: table)",
    )
    return parser


def _cf_version(arguments: argparse.Namespace) -> str:
    return str(arguments.cf_version)


def _data_directory(arguments: argparse.Namespace) -> Path | None:
    value = arguments.data_directory
    return value if isinstance(value, Path) else None


def _profile(arguments: argparse.Namespace) -> str:
    return str(arguments.profile)


def _profile_version(arguments: argparse.Namespace) -> str:
    return str(arguments.profile_version)


def _profile_directories(arguments: argparse.Namespace) -> tuple[Path, ...]:
    return tuple(arguments.profile_directory)


def _dataset_options(arguments: argparse.Namespace) -> _DatasetOptions:
    return {
        "cf_version": _cf_version(arguments),
        "profile": _profile(arguments),
        "profile_version": _profile_version(arguments),
        "data_directory": _data_directory(arguments),
        "profile_directories": _profile_directories(arguments),
    }


def _normalize_coordinate_pair_options(argv: Sequence[str]) -> list[str]:
    """Keep negative comma pairs attached so argparse does not treat them as options."""

    normalized: list[str] = []
    index = 0
    while index < len(argv):
        argument = argv[index]
        if (
            argument in {"--lonlat", "--latlon"}
            and index + 1 < len(argv)
            and argv[index + 1].startswith("-")
            and "," in argv[index + 1]
        ):
            normalized.append(f"{argument}={argv[index + 1]}")
            index += 2
            continue
        normalized.append(argument)
        index += 1
    return normalized


def _run_lookup(arguments: argparse.Namespace) -> None:
    longitude, latitude = resolve_coordinates(
        longitude=arguments.longitude,
        latitude=arguments.latitude,
        lonlat=arguments.lonlat,
        latlon=arguments.latlon,
    )
    matches = match_regions(
        longitude=longitude,
        latitude=latitude,
        section_tolerance_km=arguments.section_tolerance_km,
        include_ancestors=arguments.ancestors,
        **_dataset_options(arguments),
    )
    if arguments.format == "names":
        sys.stdout.write(_lines([match.name for match in matches]))
        return
    if arguments.format == "table":
        rows = [
            (
                match.name,
                match.relation,
                "" if match.distance_km is None else f"{match.distance_km:.3f}",
            )
            for match in matches
        ]
        sys.stdout.write(_table(("Region", "Relation", "Distance (km)"), rows))
        return
    if arguments.format == "jsonl":
        sys.stdout.write(_json_lines([match.to_dict() for match in matches]))
        return
    if arguments.format == "json":
        info = get_dataset_info(
            **_dataset_options(arguments),
        )
        payload: dict[str, Any] = {
            "longitude": longitude,
            "latitude": latitude,
            "section_tolerance_km": arguments.section_tolerance_km,
            "cf_version": info.cf_version,
            "profile": info.profile.to_dict(),
            "mapping": {
                "id": info.mapping_id,
                "version": info.mapping_version,
                "geometry_resolution": info.lookup_geometry_resolution,
                "behavior_version": info.lookup_behavior_version,
                "crs": info.crs,
                "created_at": info.generated_on,
                "geometry_sha256": info.lookup_geometry_sha256,
                "geometry_validation": info.lookup_geometry_validation,
            },
            "method": {
                "area_predicate": info.area_predicate,
                "boundary_inclusive": info.boundary_inclusive,
                "section_method": info.section_method,
                "hierarchy_results_are_geometric": False,
                "include_ancestors": arguments.ancestors,
            },
            "matches": [match.to_dict() for match in matches],
        }
        sys.stdout.write(_json(payload))
        return


def _run_regions(arguments: argparse.Namespace) -> None:
    regions = list_regions(
        **_dataset_options(arguments),
    )
    if arguments.format == "names":
        sys.stdout.write(_lines([region.name for region in regions]))
        return
    if arguments.format == "table":
        sys.stdout.write(
            _table(
                ("Region", "Kind"),
                [(region.name, region.kind) for region in regions],
            )
        )
        return
    if arguments.format == "jsonl":
        sys.stdout.write(_json_lines([region.to_dict() for region in regions]))
        return
    if arguments.format == "json":
        sys.stdout.write(_json([region.to_dict() for region in regions]))


def _run_hierarchy(arguments: argparse.Namespace) -> None:
    region_name = arguments.region_name
    edges = list_hierarchy_edges(
        region_name=region_name,
        **_dataset_options(arguments),
    )
    if arguments.format == "tree":
        regions = list_regions(
            **_dataset_options(arguments),
        )
        sys.stdout.write(
            _hierarchy_tree(
                [region.name for region in regions],
                edges,
                selected_region=region_name,
            )
        )
        return
    if arguments.format == "table":
        sys.stdout.write(
            _table(
                ("Child", "Parent", "Origin"),
                [(edge.child, edge.parent, edge.origin) for edge in edges],
            )
        )
        return
    if arguments.format == "jsonl":
        sys.stdout.write(_json_lines([edge.to_dict() for edge in edges]))
        return

    info = get_dataset_info(
        **_dataset_options(arguments),
    )
    sys.stdout.write(
        _json(
            {
                "cf_version": info.cf_version,
                "region_name": region_name,
                "profile": info.profile.to_dict(),
                "mapping": {
                    "id": info.mapping_id,
                    "version": info.mapping_version,
                },
                "hierarchy": {
                    "name": info.hierarchy_name,
                    "version": info.hierarchy_version,
                    "date": info.hierarchy_date,
                    "url": info.hierarchy_url,
                    "note": (
                        "GCMD path projections are supplemented by documented "
                        "mapping-curation links."
                    ),
                },
                "count": len(edges),
                "edges": [edge.to_dict() for edge in edges],
            }
        )
    )


def _run_shape(arguments: argparse.Namespace) -> None:
    feature = get_region_shape(
        region_name=arguments.region_name,
        geometry_resolution=arguments.geometry_resolution,
        **_dataset_options(arguments),
    )
    if arguments.format == "geojson":
        content = _json(feature)
    else:
        geometry = shapely_shape(feature["geometry"])
        if arguments.format == "wkb":
            if arguments.output is None:
                sys.stdout.buffer.write(geometry.wkb)
            else:
                arguments.output.write_bytes(geometry.wkb)
            return
        content = (
            f"{geometry.wkt}\n"
            if arguments.format == "wkt"
            else f"{geometry.wkb_hex}\n"
        )
    if arguments.output is None:
        sys.stdout.write(content)
    else:
        arguments.output.write_text(content, encoding="utf-8")


def _run_info(arguments: argparse.Namespace) -> None:
    info = get_dataset_info(
        **_dataset_options(arguments),
    )
    if arguments.format == "json":
        sys.stdout.write(_json(info.to_dict()))
        return
    sys.stdout.write(
        f"CF Standardized Region List: {info.cf_version} ({info.cf_date})\n"
        f"Spatial profile: {info.profile.id}@{info.profile.version}\n"
        f"Mapping: {info.mapping_id}@{info.mapping_version} ({info.generated_on})\n"
        f"Lookup: {info.area_predicate}, boundary inclusive; "
        f"{info.lookup_geometry_resolution} geometry\n"
        f"Rendering resolutions: "
        f"{', '.join(item.resolution for item in info.geometry_representations)}\n"
        f"Hierarchy: {info.hierarchy_name} {info.hierarchy_version} "
        f"({info.hierarchy_date})\n"
        f"CRS: {info.crs}\n"
        f"Regions: {info.region_count}\n"
    )
    for limitation in info.limitations:
        sys.stdout.write(f"Limitation: {limitation}\n")


def _run_versions(arguments: argparse.Namespace) -> None:
    for version in list_cf_versions(
        data_directory=_data_directory(arguments),
    ):
        sys.stdout.write(f"{version}\n")


def _run_profiles(arguments: argparse.Namespace) -> None:
    profiles = list_spatial_profiles(
        data_directory=_data_directory(arguments),
        profile_directories=_profile_directories(arguments),
    )
    if arguments.format == "json":
        sys.stdout.write(_json([profile.to_dict() for profile in profiles]))
        return
    rows = [
        (
            profile.id,
            profile.version,
            "yes" if profile.is_default else "",
            ", ".join(profile.cf_versions),
        )
        for profile in profiles
    ]
    sys.stdout.write(_table(("Profile", "Version", "Default", "CF versions"), rows))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface and return a process exit status."""

    parser = _build_parser()
    raw_arguments = sys.argv[1:] if argv is None else argv
    arguments = parser.parse_args(_normalize_coordinate_pair_options(raw_arguments))
    handlers = {
        "lookup": _run_lookup,
        "regions": _run_regions,
        "hierarchy": _run_hierarchy,
        "shape": _run_shape,
        "info": _run_info,
        "versions": _run_versions,
        "profiles": _run_profiles,
    }
    try:
        handlers[arguments.command](arguments)
    except (CFRegionsError, OSError) as error:
        message = str(error.args[0]) if error.args else str(error)
        parser.exit(2, f"{parser.prog}: error: {message}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
