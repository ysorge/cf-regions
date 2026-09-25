#!/usr/bin/env python3
"""Build the bundled default spatial profile from pinned upstream datasets.

The output directory is one profile-version directory containing manifest.json,
hierarchy.json, geometry/*.geojson, and an optional generated lookup artifact.
This is a maintainer tool; runtime lookups never contact upstream services.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable, Sequence
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any

import shapefile
from shapely import make_valid, set_precision
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPolygon,
    box,
    mapping,
    shape,
)
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

try:
    from .lookup_artifact import build_lookup_artifact
except ImportError:  # Direct execution: python tools/build_dataset.py
    from lookup_artifact import build_lookup_artifact

CF_URL = (
    "https://cfconventions.org/Data/standardized-region-list/"
    "standardized-region-list.5.xml"
)
GCMD_URL = (
    "https://gcmd.earthdata.nasa.gov/kms/concepts/concept_scheme/locations"
    "?format=csv&page_size=2000"
)
SEAVOX_URL = "https://www.marineregions.org/download_file.php?name=SeaVoX_sea_areas_polygons_v19.zip"
SEAVOX_SOURCE_URL = "https://doi.org/10.14284/590"
NATURAL_EARTH_URL = "https://www.naturalearthdata.com/downloads/50m-physical-vectors/"
OMIP_URL = "https://doi.org/10.5194/gmd-9-3231-2016"
CMIP_URL = "https://github.com/PCMDI/cmip6-cmor-tables"
GEOMETRY_EDITION = "2026.09.1"
MAPPING_ID = "cfregions-default"
RESOLUTION_PROFILES = {
    "low": {
        "label": "Low detail",
        "description": "Compact geometry for fast lookup and overview maps.",
        "seavox_simplification_degrees": 0.02,
        "output_simplification_degrees": 0.01,
        "coordinate_precision_degrees": 0.00001,
        "filename": "low.geojson",
    },
    "high": {
        "label": "High detail",
        "description": "More detailed geometry for closer visual inspection; slower and larger.",
        "seavox_simplification_degrees": 0.002,
        "output_simplification_degrees": 0.001,
        "coordinate_precision_degrees": 0.000001,
        "filename": "high.geojson",
    },
}

SEAVOX_SELECTORS: dict[str, tuple[str, str]] = {
    "arctic_ocean": ("mrgid_r", "23617"),
    "atlantic_ocean": ("mrgid_r", "23618"),
    "baltic_sea": ("mrgid_r", "23619"),
    "indian_ocean": ("mrgid_r", "23620"),
    "pacific_ocean": ("mrgid_r", "23622"),
    "southern_ocean": ("mrgid_r", "23624"),
    "mediterranean_sea": ("mrgid_l1", "23628"),
    "ross_sea": ("mrgid_l1", "23631"),
    "bering_sea": ("mrgid_l3", "23651"),
    "irish_sea": ("mrgid_l3", "23731"),
    "north_sea": ("mrgid_l3", "23647"),
    "sea_of_japan": ("mrgid_l3", "23648"),
    "yellow_sea": ("mrgid_l3", "23645"),
    "arabian_sea": ("mrgid_sr", "24074"),
    "aral_sea": ("mrgid_sr", "24176"),
    "barents_sea": ("mrgid_sr", "24029"),
    "beaufort_sea": ("mrgid_sr", "24023"),
    "bellingshausen_sea": ("mrgid_sr", "24148"),
    "black_sea": ("mrgid_sr", "24093"),
    "caribbean_sea": ("mrgid_sr", "24042"),
    "caspian_sea": ("mrgid_sr", "24175"),
    "chukchi_sea": ("mrgid_sr", "24022"),
    "east_china_sea": ("mrgid_sr", "24107"),
    "gulf_of_alaska": ("mrgid_sr", "24118"),
    "gulf_of_mexico": ("mrgid_sr", "24044"),
    "hudson_bay": ("mrgid_sr", "24018"),
    "norwegian_sea": ("mrgid_sr", "24024"),
    "persian_gulf": ("mrgid_sr", "24080"),
    "red_sea": ("mrgid_sr", "24077"),
    "sea_of_okhotsk": ("mrgid_sr", "24120"),
    "weddell_sea": ("mrgid_sr", "24035"),
}

NVS_IDS = {
    "atlantic_arctic_ocean": "CFSRLAAO",
    "indian_pacific_ocean": "CFSRLIPO",
    "northern_hemisphere": "NORTHHEM",
    "southern_hemisphere": "SOUTHHEM",
    "contiguous_united_states": "cfcounst",
    "barents_opening": "cfbarope",
    "bering_strait": "cfberstr",
    "canadian_archipelago": "cfcanarc",
    "davis_strait": "cfdaviss",
    "denmark_strait": "cfdenstr",
    "drake_passage": "cfdrapas",
    "english_channel": "cfengcha",
    "faroe_scotland_channel": "cffascch",
    "florida_bahamas_strait": "cfflbast",
    "fram_strait": "cffrastr",
    "gibraltar_strait": "cfgibral",
    "iceland_faroe_channel": "cficfach",
    "indonesian_throughflow": "cfindthr",
    "mozambique_channel": "cfmozcha",
    "pacific_equatorial_undercurrent": "cfpaequn",
    "taiwan_luzon_straits": "cftalust",
    "windward_passage": "cfwinpas",
}

PARENTS: dict[str, tuple[str, ...]] = {
    "global_land": ("global",),
    "global_ocean": ("global",),
    "northern_hemisphere": ("global",),
    "southern_hemisphere": ("global",),
    "africa": ("global_land",),
    "antarctica": ("global_land",),
    "australia": ("global_land",),
    "eurasia": ("global_land",),
    "north_america": ("global_land",),
    "south_america": ("global_land",),
    "asia": ("eurasia",),
    "europe": ("eurasia",),
    "central_america": ("north_america",),
    "contiguous_united_states": ("north_america",),
    "greenland": ("north_america",),
    "arctic_ocean": ("global_ocean",),
    "atlantic_ocean": ("global_ocean",),
    "indian_ocean": ("global_ocean",),
    "pacific_ocean": ("global_ocean",),
    "southern_ocean": ("global_ocean",),
    "atlantic_arctic_ocean": ("global_ocean",),
    "indian_pacific_ocean": ("global_ocean",),
    "indo_pacific_ocean": ("global_ocean",),
    "arabian_sea": ("indian_ocean",),
    "aral_sea": ("asia",),
    "baltic_sea": ("atlantic_ocean",),
    "barents_sea": ("arctic_ocean",),
    "beaufort_sea": ("arctic_ocean",),
    "bellingshausen_sea": ("southern_ocean",),
    "bering_sea": ("pacific_ocean",),
    "black_sea": ("asia", "europe"),
    "caribbean_sea": ("atlantic_ocean",),
    "caspian_sea": ("asia",),
    "chukchi_sea": ("arctic_ocean",),
    "east_china_sea": ("pacific_ocean",),
    "gulf_of_alaska": ("pacific_ocean",),
    "gulf_of_mexico": ("atlantic_ocean",),
    "hudson_bay": ("north_america",),
    "irish_sea": ("atlantic_ocean",),
    "mediterranean_sea": ("atlantic_ocean",),
    "north_sea": ("atlantic_ocean",),
    "norwegian_sea": ("atlantic_ocean",),
    "persian_gulf": ("arabian_sea",),
    "red_sea": ("indian_ocean",),
    "ross_sea": ("southern_ocean",),
    "sea_of_japan": ("pacific_ocean",),
    "sea_of_okhotsk": ("pacific_ocean",),
    "south_china_sea": ("pacific_ocean",),
    "weddell_sea": ("southern_ocean",),
    "yellow_sea": ("pacific_ocean",),
    "great_lakes": ("north_america",),
    "lake_baykal": ("europe",),
    "lake_chad": ("africa",),
    "lake_malawi": ("africa",),
    "lake_tanganyika": ("africa",),
    "lake_victoria": ("africa",),
    "barents_opening": ("barents_sea", "norwegian_sea"),
    "bering_strait": ("bering_sea", "chukchi_sea"),
    "canadian_archipelago": ("arctic_ocean", "atlantic_ocean"),
    "davis_strait": ("atlantic_ocean",),
    "denmark_strait": ("atlantic_ocean", "arctic_ocean"),
    "drake_passage": ("southern_ocean",),
    "english_channel": ("atlantic_ocean",),
    "faroe_scotland_channel": ("atlantic_ocean",),
    "florida_bahamas_strait": ("atlantic_ocean",),
    "fram_strait": ("arctic_ocean", "atlantic_ocean"),
    "gibraltar_strait": ("atlantic_ocean", "mediterranean_sea"),
    "iceland_faroe_channel": ("atlantic_ocean",),
    "indonesian_throughflow": ("indian_ocean", "pacific_ocean"),
    "mozambique_channel": ("indian_ocean",),
    "pacific_equatorial_undercurrent": ("pacific_ocean",),
    "taiwan_luzon_straits": ("pacific_ocean", "south_china_sea"),
    "windward_passage": ("caribbean_sea", "atlantic_ocean"),
}

SECTION_COORDINATES: dict[str, list[list[list[float]]]] = {
    "barents_opening": [[[16.8, 76.5], [19.2, 70.2]]],
    "bering_strait": [[[-171.0, 66.2], [-166.0, 65.0]]],
    "canadian_archipelago": [[[-128.2, 70.6], [-59.3, 82.1]]],
    "davis_strait": [[[-50.0, 65.0], [-65.0, 65.0]]],
    "denmark_strait": [[[-37.0, 66.1], [-22.5, 66.0]]],
    "drake_passage": [[[-68.0, -54.0], [-60.0, -64.7]]],
    "english_channel": [[[1.5, 51.1], [1.7, 51.0]]],
    "faroe_scotland_channel": [[[-6.9, 62.0], [-5.0, 58.7]]],
    "florida_bahamas_strait": [[[-78.5, 26.0], [-80.5, 27.0]]],
    "fram_strait": [
        [[-20.0, 79.0], [11.0, 79.0]],
        [[-11.5, 81.3], [10.5, 79.6]],
    ],
    "gibraltar_strait": [[[-5.6, 35.8], [-5.6, 36.0]]],
    "iceland_faroe_channel": [[[-13.6, 64.9], [-7.4, 62.2]]],
    "indonesian_throughflow": [[[100.0, -6.0], [140.0, -6.0]]],
    "mozambique_channel": [[[39.0, -16.0], [45.0, -18.0]]],
    "pacific_equatorial_undercurrent": [[[-155.0, -2.0], [-155.0, 2.0]]],
    "taiwan_luzon_straits": [[[121.8, 18.3], [121.8, 22.3]]],
    "windward_passage": [[[-75.0, 20.2], [-72.6, 19.7]]],
}

LOWER_48_AND_DC = {
    "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "IA", "ID",
    "IL", "IN", "KS", "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS",
    "MT", "NC", "ND", "NE", "NH", "NJ", "NM", "NV", "NY", "OH", "OK", "OR",
    "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VA", "VT", "WA", "WI", "WV",
    "WY",
}


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cf-xml", type=Path, required=True)
    parser.add_argument("--gcmd-csv", type=Path, required=True)
    parser.add_argument("--seavox", type=Path, nargs="+", required=True)
    parser.add_argument("--ne-regions", type=Path, required=True)
    parser.add_argument("--ne-marine", type=Path, required=True)
    parser.add_argument("--ne-lakes", type=Path, required=True)
    parser.add_argument("--ne-land", type=Path, required=True)
    parser.add_argument("--ne-ocean", type=Path, required=True)
    parser.add_argument("--ne-admin1", type=Path, required=True)
    parser.add_argument(
        "--geometry-resolution",
        choices=tuple(RESOLUTION_PROFILES),
        default="low",
        help="representation to build (default: low)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            Path("src/cfregions/data/profiles")
            / MAPPING_ID
            / GEOMETRY_EDITION
        ),
        help="profile-version output directory (default: bundled default profile)",
    )
    return parser.parse_args()


def _read_cf(path: Path) -> tuple[dict[str, str], str, str]:
    root = ET.parse(path).getroot()
    descriptions = {
        entry.attrib["id"]: (entry.findtext("description") or "").strip()
        for entry in root.findall("entry")
    }
    return descriptions, root.findtext("version_number", ""), root.findtext("date", "")


def _normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _read_gcmd_paths(path: Path, names: set[str]) -> dict[str, tuple[str, ...]]:
    result: dict[str, list[tuple[str, ...]]] = {name: [] for name in names}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        next(handle)
        reader = csv.DictReader(handle)
        location_fields = [field for field in reader.fieldnames or () if field != "UUID"]
        for row in reader:
            values = tuple(row[field] for field in location_fields if row[field])
            if not values:
                continue
            normalized = _normalize_label(values[-1])
            if normalized in result:
                result[normalized].append(values)
    return {
        name: min(paths, key=lambda item: (len(item), item)) if paths else ()
        for name, paths in result.items()
    }


def _read_shapes(
    path: Path, predicate: Callable[[dict[str, Any]], bool] | None = None
) -> list[BaseGeometry]:
    reader = shapefile.Reader(str(path))
    geometries: list[BaseGeometry] = []
    for shape_record in reader.iterShapeRecords():
        properties = shape_record.record.as_dict()
        if predicate is None or predicate(properties):
            geometries.append(shape(shape_record.shape.__geo_interface__))
    return geometries


def _polygonal(geometry: BaseGeometry) -> BaseGeometry:
    valid = make_valid(geometry) if not geometry.is_valid else geometry
    if valid.geom_type in {"Polygon", "MultiPolygon"}:
        return valid
    if isinstance(valid, GeometryCollection):
        polygons: list[BaseGeometry] = []
        for part in valid.geoms:
            if part.geom_type == "Polygon":
                polygons.append(part)
            elif part.geom_type == "MultiPolygon":
                polygons.extend(part.geoms)  # type: ignore[arg-type]
        if polygons:
            return unary_union(polygons)
    raise ValueError(f"expected polygonal geometry, got {valid.geom_type}")


def _dissolve(geometries: Iterable[BaseGeometry]) -> BaseGeometry:
    items = list(geometries)
    if not items:
        raise ValueError("cannot dissolve an empty geometry selection")
    return _polygonal(unary_union(items))


def _prepare(
    geometry: BaseGeometry,
    *,
    simplify_degrees: float,
    precision_degrees: float,
) -> BaseGeometry:
    result = _polygonal(geometry)
    if simplify_degrees > 0:
        result = _polygonal(
            result.simplify(simplify_degrees, preserve_topology=True)
        )
    return _polygonal(set_precision(result, grid_size=precision_degrees))


def _load_seavox(paths: Sequence[Path]) -> list[dict[str, Any]]:
    by_identifier: dict[str, dict[str, Any]] = {}
    for path in paths:
        if path.suffix.lower() == ".shp":
            reader = shapefile.Reader(str(path))
            source_features = []
            for index, record in enumerate(reader.iterShapeRecords()):
                properties = {
                    str(key).lower(): value for key, value in record.record.as_dict().items()
                }
                source_features.append({
                    "type": "Feature",
                    "id": str(properties.get("mrgid_sr", f"{path.name}:{index}")),
                    "properties": properties,
                    "geometry": record.shape.__geo_interface__,
                })
        else:
            document = json.loads(path.read_text(encoding="utf-8"))
            source_features = document["features"]
        for feature in source_features:
            identifier = str(feature.get("id", len(by_identifier)))
            existing = by_identifier.get(identifier)
            if existing is None or len(feature.get("properties", {})) > len(
                existing.get("properties", {})
            ):
                by_identifier[identifier] = feature
    return list(by_identifier.values())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _shapefile_parts(path: Path) -> list[Path]:
    parts = [path.with_suffix(suffix) for suffix in (".shp", ".shx", ".dbf", ".prj", ".cpg")]
    version_file = path.with_name(f"{path.stem}.VERSION.txt")
    return [part for part in [*parts, version_file] if part.exists()]


def _assert_natural_earth_version(path: Path, expected: str) -> None:
    version_file = path.with_name(f"{path.stem}.VERSION.txt")
    if not version_file.exists():
        raise ValueError(f"missing Natural Earth version file: {version_file}")
    actual = version_file.read_text(encoding="utf-8").strip()
    if actual != expected:
        raise ValueError(
            f"expected Natural Earth {path.stem} version {expected}, found {actual}"
        )


def _specificity(name: str, parents: tuple[str, ...], kind: str) -> int:
    if kind == "section":
        return 100
    fixed = {
        "global": 0,
        "northern_hemisphere": 5,
        "southern_hemisphere": 5,
        "global_land": 10,
        "global_ocean": 10,
        "eurasia": 20,
        "atlantic_arctic_ocean": 20,
        "indian_pacific_ocean": 20,
        "indo_pacific_ocean": 25,
        "africa": 30,
        "antarctica": 30,
        "asia": 30,
        "australia": 30,
        "europe": 30,
        "north_america": 30,
        "south_america": 30,
        "arctic_ocean": 30,
        "atlantic_ocean": 30,
        "indian_ocean": 30,
        "pacific_ocean": 30,
        "southern_ocean": 30,
        "central_america": 50,
        "contiguous_united_states": 60,
        "greenland": 50,
        "persian_gulf": 80,
    }
    return fixed.get(name, 70 if parents else 40)


def _feature(
    *,
    name: str,
    geometry: BaseGeometry,
    source: str,
    source_url: str,
    source_version: str,
    license_name: str,
    method: str,
    kind: str = "area",
    contexts: tuple[str, ...] = (),
) -> dict[str, Any]:
    parents = PARENTS.get(name, ())
    return {
        "type": "Feature",
        "id": name,
        "properties": {
            "name": name,
            "kind": kind,
            "nvs_concept_url": (
                f"https://vocab.nerc.ac.uk/collection/P30/5/{NVS_IDS.get(name, name)}/"
            ),
            "geometry_source": source,
            "geometry_source_url": source_url,
            "geometry_source_version": source_version,
            "geometry_license": license_name,
            "geometry_method": method,
            "geometry_contexts": list(contexts),
            "specificity": _specificity(name, parents, kind),
        },
        "geometry": mapping(geometry),
    }


def main() -> None:
    arguments = _arguments()
    profile = RESOLUTION_PROFILES[arguments.geometry_resolution]
    prepare = partial(
        _prepare,
        simplify_degrees=float(profile["output_simplification_degrees"]),
        precision_degrees=float(profile["coordinate_precision_degrees"]),
    )
    descriptions, cf_version, _cf_date = _read_cf(arguments.cf_xml)
    expected_names = set(descriptions)
    if len(expected_names) != 74:
        raise ValueError(f"expected 74 CF v5 names, found {len(expected_names)}")
    if set(PARENTS) != expected_names - {"global"}:
        raise ValueError("the curated hierarchy must connect every non-global CF name")
    for region_name, parent_names in PARENTS.items():
        unknown = set(parent_names) - expected_names
        if unknown:
            raise ValueError(f"{region_name} refers to unknown parents: {sorted(unknown)}")
    for path, expected_version in (
        (arguments.ne_regions, "5.0.0"),
        (arguments.ne_marine, "5.1.0"),
        (arguments.ne_lakes, "5.0.0"),
        (arguments.ne_land, "4.1.0"),
        (arguments.ne_ocean, "4.1.0"),
        (arguments.ne_admin1, "5.1.1"),
    ):
        _assert_natural_earth_version(path, expected_version)
    hierarchy_paths = _read_gcmd_paths(arguments.gcmd_csv, expected_names)

    print("loading SeaVoX source features", flush=True)
    seavox_features = _load_seavox(arguments.seavox)
    print(f"loaded {len(seavox_features)} unique SeaVoX features", flush=True)
    prepared_seavox: list[tuple[dict[str, Any], BaseGeometry]] = []
    for index, feature in enumerate(seavox_features, start=1):
        source_geometry = _polygonal(shape(feature["geometry"]))
        simplified = _polygonal(
            source_geometry.simplify(
                float(profile["seavox_simplification_degrees"]),
                preserve_topology=False,
            )
        )
        prepared_seavox.append((feature.get("properties", {}), simplified))
        if index % 25 == 0:
            print(f"simplified {index}/{len(seavox_features)} SeaVoX features", flush=True)
    del seavox_features
    print("simplified SeaVoX source features", flush=True)
    geometries: dict[str, BaseGeometry] = {}
    metadata: dict[str, tuple[str, str, str, str, str]] = {}
    for name, (field, identifier) in SEAVOX_SELECTORS.items():
        selected = [
            geometry
            for properties, geometry in prepared_seavox
            if str(properties.get(field)) == identifier
        ]
        if not selected:
            raise ValueError(f"no SeaVoX features for {name}: {field}={identifier}")
        geometries[name] = prepare(_dissolve(selected))
        metadata[name] = (
            "SeaVoX Salt and Fresh Water Body Gazetteer polygons",
            SEAVOX_SOURCE_URL,
            "19",
            "CC BY 4.0",
            f"dissolved all SeaVoX v19 features where {field}={identifier}",
        )
        print(f"built {name} from {len(selected)} SeaVoX feature(s)", flush=True)

    print("building Natural Earth land regions and lakes", flush=True)
    region_reader = shapefile.Reader(str(arguments.ne_regions))
    region_by_name: dict[str, list[BaseGeometry]] = {}
    for shape_record in region_reader.iterShapeRecords():
        region_name = str(shape_record.record.as_dict()["NAME"]).upper()
        region_by_name.setdefault(region_name, []).append(
            shape(shape_record.shape.__geo_interface__)
        )
    for name, source_name in {
        "africa": "AFRICA",
        "antarctica": "ANTARCTICA",
        "asia": "ASIA",
        "australia": "AUSTRALIA",
        "central_america": "CENTRAL AMERICA",
        "europe": "EUROPE",
        "greenland": "GREENLAND",
        "north_america": "NORTH AMERICA",
        "south_america": "SOUTH AMERICA",
    }.items():
        geometries[name] = prepare(_dissolve(region_by_name[source_name]))
        metadata[name] = (
            "Natural Earth geography regions",
            "https://www.naturalearthdata.com/downloads/50m-physical-vectors/50m-physical-labels/",
            "5.0.0",
            "Public domain",
            f"selected Natural Earth geography region {source_name}",
        )
    geometries["eurasia"] = prepare(unary_union([geometries["asia"], geometries["europe"]]))
    metadata["eurasia"] = (
        "Natural Earth geography regions",
        "https://www.naturalearthdata.com/",
        "5.0.0",
        "Public domain",
        "union of the bundled Asia and Europe interpretations",
    )

    lower_states = _read_shapes(
        arguments.ne_admin1,
        lambda record: record.get("adm0_a3") == "USA"
        and record.get("postal") in LOWER_48_AND_DC,
    )
    if len(lower_states) != 49:
        raise ValueError(f"expected lower 48 states plus DC, selected {len(lower_states)}")
    geometries["contiguous_united_states"] = prepare(_dissolve(lower_states))
    metadata["contiguous_united_states"] = (
        "Natural Earth admin-1 states and provinces",
        "https://www.naturalearthdata.com/downloads/50m-cultural-vectors/50m-admin-1-states-provinces/",
        "5.1.1",
        "Public domain",
        (
            "union of the lower 48 United States and District of Columbia "
            "(postal codes pinned in builder)"
        ),
    )

    lake_reader = shapefile.Reader(str(arguments.ne_lakes))
    lakes_by_name: dict[str, list[BaseGeometry]] = {}
    for shape_record in lake_reader.iterShapeRecords():
        lake_name = str(shape_record.record.as_dict().get("name", ""))
        lakes_by_name.setdefault(lake_name, []).append(shape(shape_record.shape.__geo_interface__))
    lake_selections = {
        "great_lakes": [
            "Lake Erie", "Lake Huron", "Lake Michigan", "Lake Ontario", "Lake Superior"
        ],
        "lake_baykal": ["Lake Baikal"],
        "lake_chad": ["Lake Chad"],
        "lake_malawi": ["Lake Malawi"],
        "lake_tanganyika": ["Lake Tanganyika"],
        "lake_victoria": ["Lake Victoria"],
    }
    for name, selected_names in lake_selections.items():
        selected = [geometry for value in selected_names for geometry in lakes_by_name[value]]
        geometries[name] = prepare(_dissolve(selected))
        metadata[name] = (
            "Natural Earth lakes",
            "https://www.naturalearthdata.com/downloads/50m-physical-vectors/50m-lakes/",
            "5.0.0",
            "Public domain",
            "union of Natural Earth features: " + ", ".join(selected_names),
        )

    marine_reader = shapefile.Reader(str(arguments.ne_marine))
    south_china = [
        shape(item.shape.__geo_interface__)
        for item in marine_reader.iterShapeRecords()
        if item.record.as_dict().get("name") == "South China Sea"
    ]
    geometries["south_china_sea"] = prepare(_dissolve(south_china))
    metadata["south_china_sea"] = (
        "Natural Earth geography marine polygons",
        "https://www.naturalearthdata.com/downloads/50m-physical-vectors/50m-physical-labels/",
        "5.1.0",
        "Public domain",
        "selected Natural Earth marine polygon South China Sea; SeaVoX v19 has no exact geometry",
    )

    print("building global land and ocean masks", flush=True)
    geometries["global_land"] = prepare(_dissolve(_read_shapes(arguments.ne_land)))
    geometries["global_ocean"] = prepare(_dissolve(_read_shapes(arguments.ne_ocean)))
    for name, layer in (("global_land", "land"), ("global_ocean", "ocean")):
        metadata[name] = (
            f"Natural Earth {layer}",
            NATURAL_EARTH_URL,
            "4.1.0",
            "Public domain",
            f"dissolved Natural Earth 1:50m {layer} polygons",
        )

    geometries["global"] = box(-180.0, -90.0, 180.0, 90.0)
    geometries["northern_hemisphere"] = box(-180.0, 0.0, 180.0, 90.0)
    geometries["southern_hemisphere"] = box(-180.0, -90.0, 180.0, 0.0)
    for name, method in {
        "global": "WGS84 world extent",
        "northern_hemisphere": "WGS84 world extent north of and including the equator",
        "southern_hemisphere": "WGS84 world extent south of and including the equator",
    }.items():
        metadata[name] = (
            "cf-regions analytical geometry",
            "https://github.com/ysorge/cf-regions",
            GEOMETRY_EDITION,
            "Apache-2.0",
            method,
        )

    geometries["atlantic_arctic_ocean"] = prepare(
        unary_union([geometries["atlantic_ocean"], geometries["arctic_ocean"]])
    )
    geometries["indian_pacific_ocean"] = prepare(
        unary_union([geometries["indian_ocean"], geometries["pacific_ocean"]])
    )
    tropical_indo_pacific = MultiPolygon(
        [
            box(20.0, -23.43666, 180.0, 23.43666),
            box(-180.0, -23.43666, -140.0, 23.43666),
        ]
    )
    geometries["indo_pacific_ocean"] = prepare(
        geometries["global_ocean"].intersection(tropical_indo_pacific)
    )
    for name, method in {
        "atlantic_arctic_ocean": "union of the SeaVoX Atlantic and Arctic interpretations",
        "indian_pacific_ocean": "union of the SeaVoX Indian and Pacific interpretations",
        "indo_pacific_ocean": (
            "interpretation of CF's biogeographic definition: Natural Earth ocean within "
            "the tropics, from 20E eastward through 140W"
        ),
    }.items():
        metadata[name] = (
            "cf-regions derived geometry",
            CF_URL,
            GEOMETRY_EDITION,
            "Derived from CC BY 4.0 and/or public-domain geometries",
            method,
        )

    print("serializing region features", flush=True)
    features: list[dict[str, Any]] = []
    for name in sorted(geometries):
        features.append(
            _feature(
                name=name,
                geometry=geometries[name],
                source=metadata[name][0],
                source_url=metadata[name][1],
                source_version=metadata[name][2],
                license_name=metadata[name][3],
                method=metadata[name][4],
            )
        )

    for name, parts in SECTION_COORDINATES.items():
        geometry: BaseGeometry = (
            LineString(parts[0]) if len(parts) == 1 else MultiLineString(parts)
        )
        is_canadian = name == "canadian_archipelago"
        is_fram = name == "fram_strait"
        source = "CMIP6 CMOR tables" if is_canadian else "OMIP protocol Table J1"
        source_url = CMIP_URL if is_canadian else OMIP_URL
        license_name = "BSD-3-Clause" if is_canadian else "CC BY 3.0"
        contexts: tuple[str, ...] = ()
        method = "approximate diagnostic section endpoints"
        if is_fram:
            source = "OMIP protocol Table J1 and CMIP6 CMOR tables"
            source_url = f"{OMIP_URL}; {CMIP_URL}"
            license_name = "CC BY 3.0 and BSD-3-Clause"
            contexts = ("ocean_mass_transport", "sea_ice_transport")
            method = "two approximate diagnostic section variants retained as a MultiLineString"
        elif name == "pacific_equatorial_undercurrent":
            contexts = ("ocean_mass_transport_at_0_to_350_m_depth",)
        features.append(
            _feature(
                name=name,
                geometry=geometry,
                source=source,
                source_url=source_url,
                source_version="2016 / CMIP6",
                license_name=license_name,
                method=method,
                kind="section",
                contexts=contexts,
            )
        )

    features.sort(key=lambda feature: feature["properties"]["name"])
    actual_names = {feature["properties"]["name"] for feature in features}
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        extra = sorted(actual_names - expected_names)
        raise ValueError(f"CF name mismatch; missing={missing}, extra={extra}")

    geometry_dir = arguments.output_dir / "geometry"
    geometry_dir.mkdir(parents=True, exist_ok=True)
    collection = {
        "$schema": "../../../../schemas/geometry.schema.json",
        "type": "FeatureCollection",
        "name": f"cf-regions geometry interpretation {GEOMETRY_EDITION}",
        "features": features,
    }
    geometry_path = geometry_dir / str(profile["filename"])
    geometry_path.write_text(
        json.dumps(collection, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    shapefiles = [
        arguments.ne_regions,
        arguments.ne_marine,
        arguments.ne_lakes,
        arguments.ne_land,
        arguments.ne_ocean,
        arguments.ne_admin1,
    ]
    all_inputs = [
        arguments.cf_xml,
        arguments.gcmd_csv,
        *(
            part
            for seavox_path in arguments.seavox
            for part in (
                _shapefile_parts(seavox_path)
                if seavox_path.suffix.lower() == ".shp"
                else [seavox_path]
            )
        ),
        *(part for shapefile_path in shapefiles for part in _shapefile_parts(shapefile_path)),
    ]
    representations = {}
    for resolution, representation_profile in RESOLUTION_PROFILES.items():
        representation_path = geometry_dir / str(
            representation_profile["filename"]
        )
        if representation_path.exists():
            representations[resolution] = {
                "label": representation_profile["label"],
                "description": representation_profile["description"],
                "geometry_file": f"geometry/{representation_profile['filename']}",
                "sha256": _sha256(representation_path),
                "feature_count": len(features),
                "processing": {
                    "method": "simplify_and_round",
                    "parameters": {
                        "seavox_pre_simplification_degrees": representation_profile[
                            "seavox_simplification_degrees"
                        ],
                        "seavox_pre_simplification_preserves_topology": False,
                        "output_simplification_degrees": representation_profile[
                            "output_simplification_degrees"
                        ],
                        "output_simplification_preserves_topology": True,
                        "coordinate_precision_degrees": representation_profile[
                            "coordinate_precision_degrees"
                        ],
                    },
                },
            }
    if "low" not in representations:
        raise ValueError("build the low representation before the high representation")
    lookup_resolution = "high" if "high" in representations else "low"
    if lookup_resolution == "high":
        high_path = geometry_dir / str(RESOLUTION_PROFILES["high"]["filename"])
        artifact_path = geometry_dir / "high.lookup.wkb"
        index_path = geometry_dir / "high.lookup.json"
        artifact_sha256, index_sha256 = build_lookup_artifact(
            high_path,
            artifact_path,
            index_path,
        )
        representations["high"]["lookup_artifact"] = {
            "format": "wkb-pack-v1",
            "geometry_file": "geometry/high.lookup.wkb",
            "index_file": "geometry/high.lookup.json",
            "sha256": artifact_sha256,
            "index_sha256": index_sha256,
        }

    hierarchy_edges = []
    for child, parents in sorted(PARENTS.items()):
        context_path = hierarchy_paths.get(child, ())
        normalized_path = {_normalize_label(value) for value in context_path}
        for parent in parents:
            from_gcmd = parent in normalized_path
            hierarchy_edges.append(
                {
                    "child": child,
                    "parent": parent,
                    "relation": "broader",
                    "origin": (
                        "gcmd_path_projection" if from_gcmd else "mapping_curation"
                    ),
                    "source": (
                        {
                            "name": "NASA GCMD Location Keywords",
                            "version": "24.8",
                            "uri": GCMD_URL,
                            "license": (
                                "NASA ESDIS open-data guidance; acknowledgment requested"
                            ),
                            "method": (
                                "parent name occurs in the retained GCMD location path"
                            ),
                        }
                        if from_gcmd
                        else {
                            "name": "cf-regions mapping curation",
                            "version": GEOMETRY_EDITION,
                            "uri": (
                                "https://github.com/ysorge/cf-regions/blob/main/"
                                "docs/mapping-guidelines.md"
                            ),
                            "license": "Apache-2.0",
                            "method": (
                                "documented composite, global, or section connectivity "
                                "link; not evidenced by the retained GCMD path"
                            ),
                        }
                    ),
                    "source_path": list(context_path) if from_gcmd else [],
                    "context_path": list(context_path),
                }
            )
    hierarchy_document = {
        "$schema": "../../../schemas/hierarchy.schema.json",
        "schema_version": 1,
        "edges": hierarchy_edges,
    }
    hierarchy_path = arguments.output_dir / "hierarchy.json"
    hierarchy_path.write_text(
        json.dumps(hierarchy_document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "$schema": "../../../schemas/profile-manifest.schema.json",
        "schema_version": 1,
        "profile": {
            "id": MAPPING_ID,
            "version": GEOMETRY_EDITION,
            "title": "cf-regions default spatial interpretation",
            "description": (
                "The bundled, documented interpretation of CF standardized region "
                "names used by cf-regions."
            ),
            "basis": (
                "CF supplies the standardized names and descriptions; NASA GCMD "
                "informs the hierarchy; SeaVoX and Natural Earth supply most area "
                "geometry; OMIP and CMIP6 inform diagnostic sections."
            ),
            "scope": (
                "General-purpose coordinate lookup, hierarchy traversal, and "
                "visualization; not for navigation or legal boundaries."
            ),
            "license": (
                "Mixed open-data terms; see DATA_LICENSES.md and this manifest."
            ),
            "homepage": "https://github.com/ysorge/cf-regions",
        },
        "supported_cf_versions": ["1", "2", "3", "4", "5"],
        "generated_on": date.today().isoformat(),
        "crs": "OGC:CRS84",
        "lookup": {
            "behavior_version": "1",
            "geometry_resolution": lookup_resolution,
            "default_geometry_resolution": "low",
            "area_predicate": "covers",
            "boundary_inclusive": True,
            "section_method": "minor_great_circle_distance",
        },
        "representations": representations,
        "hierarchy": {
            "name": "NASA GCMD Location Keywords",
            "version": "24.8",
            "date": "2026-09-16",
            "url": GCMD_URL,
            "hierarchy_file": "hierarchy.json",
            "sha256": _sha256(hierarchy_path),
            "edge_count": len(hierarchy_edges),
        },
        "limitations": [
            (
                "CF standardizes region names but does not publish canonical boundaries; "
                "every geometry is a documented interpretation."
            ),
            (
                "Natural Earth and SeaVoX geometries are generalized and must not be "
                "used for navigation or legal boundaries."
            ),
            (
                "The Indo-Pacific polygon is an explicit approximation of the CF "
                "biogeographic description."
            ),
            (
                "Diagnostic passage and transect names are lines and only participate "
                "in lookup when a positive section tolerance is supplied."
            ),
            (
                "GCMD-derived parent links are supplemented by documented composite "
                "and section connectivity links."
            ),
            (
                "Adjacent named regions need not share a boundary: SeaVoX definitions "
                "are retained without project-specific gap filling, including the North "
                "Sea and Baltic Sea."
            ),
            (
                "Resolution changes geometric detail, not the upstream definition; "
                f"coordinate lookup uses the declared {lookup_resolution} representation"
                " while low remains the default shape for compact display."
            ),
        ],
        "sources": [
            {
                "name": "CF Standardized Region List",
                "version": cf_version,
                "url": CF_URL,
                "license": "CC0",
            },
            {"name": "NASA GCMD Location Keywords", "version": "24.8", "url": GCMD_URL},
            {
                "name": "SeaVoX polygons",
                "version": "19",
                "url": SEAVOX_URL,
                "doi": "10.14284/590",
                "license": "CC BY 4.0",
            },
            {
                "name": "Natural Earth",
                "scale": "1:50m",
                "url": "https://www.naturalearthdata.com/",
                "license": "Public domain",
            },
            {"name": "OMIP protocol Table J1", "url": OMIP_URL, "license": "CC BY 3.0"},
            {"name": "CMIP6 CMOR tables", "url": CMIP_URL, "license": "BSD-3-Clause"},
        ],
        "input_sha256": {path.name: _sha256(path) for path in all_inputs},
    }
    (arguments.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {len(features)} features to {geometry_path}"
    )


if __name__ == "__main__":
    main()
