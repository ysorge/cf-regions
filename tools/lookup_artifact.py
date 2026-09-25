#!/usr/bin/env python3
"""Compile a GeoJSON representation into an optional lazy WKB lookup artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from shapely import to_wkb
from shapely.geometry import shape


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def build_lookup_artifact(
    geojson_path: Path,
    geometry_path: Path,
    index_path: Path,
) -> tuple[str, str]:
    """Write a WKB pack and JSON index; return their SHA-256 digests."""

    source_content = geojson_path.read_bytes()
    collection = json.loads(source_content)
    if not isinstance(collection, dict) or collection.get("type") != "FeatureCollection":
        raise ValueError(f"{geojson_path} is not a GeoJSON FeatureCollection")
    features = collection.get("features")
    if not isinstance(features, list):
        raise ValueError(f"{geojson_path} does not contain a feature array")

    packed = bytearray()
    records: list[dict[str, Any]] = []
    names: set[str] = set()
    for feature in features:
        if not isinstance(feature, dict):
            raise ValueError("GeoJSON contains an invalid feature")
        properties = feature.get("properties")
        raw_geometry = feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(raw_geometry, dict):
            raise ValueError("GeoJSON feature lacks properties or geometry")
        name = properties.get("name")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError(f"invalid or duplicate region name: {name!r}")
        names.add(name)
        geometry = shape(raw_geometry)
        if geometry.is_empty or not geometry.is_valid:
            raise ValueError(f"invalid geometry for {name}")
        encoded = to_wkb(geometry, byte_order=1, output_dimension=2)
        offset = len(packed)
        packed.extend(encoded)
        records.append(
            {
                "name": name,
                "geometry_type": geometry.geom_type,
                "bounds": list(geometry.bounds),
                "offset": offset,
                "length": len(encoded),
                "properties": properties,
            }
        )

    geometry_content = bytes(packed)
    index = {
        "$schema": "../../../../schemas/lookup-index.schema.json",
        "schema_version": 1,
        "format": "wkb-pack-v1",
        "source_sha256": _sha256(source_content),
        "feature_count": len(records),
        "features": records,
    }
    index_content = (json.dumps(index, indent=2) + "\n").encode()
    geometry_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    geometry_path.write_bytes(geometry_content)
    index_path.write_bytes(index_content)
    return _sha256(geometry_content), _sha256(index_content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("geojson", type=Path)
    parser.add_argument("geometry_output", type=Path)
    parser.add_argument("index_output", type=Path)
    args = parser.parse_args()
    geometry_sha256, index_sha256 = build_lookup_artifact(
        args.geojson,
        args.geometry_output,
        args.index_output,
    )
    print(f"geometry sha256: {geometry_sha256}")
    print(f"index sha256: {index_sha256}")


if __name__ == "__main__":
    main()
