from __future__ import annotations

import json
from pathlib import Path

import shapefile
from shapely import from_wkb
from tools.build_dataset import _load_seavox, _shapefile_parts
from tools.lookup_artifact import build_lookup_artifact


def test_seavox_loader_accepts_official_shapefile_style_fields(tmp_path: Path) -> None:
    path = tmp_path / "SeaVoX_sea_areas_polygons_v19.shp"
    with shapefile.Writer(str(path), shapeType=shapefile.POLYGON) as writer:
        writer.field("MRGID_SR", "C")
        writer.field("MRGID_R", "C")
        writer.poly([[[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]]])
        writer.record("24074", "23620")

    features = _load_seavox([path])

    assert len(features) == 1
    assert features[0]["id"] == "24074"
    assert features[0]["properties"]["mrgid_sr"] == "24074"
    assert features[0]["properties"]["mrgid_r"] == "23620"
    assert {part.suffix for part in _shapefile_parts(path)} == {".shp", ".shx", ".dbf"}


def test_seavox_loader_deduplicates_wfs_subsets_and_keeps_richer_properties(
    tmp_path: Path,
) -> None:
    geometry = {
        "type": "Polygon",
        "coordinates": [[[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 0.0]]],
    }
    sparse = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "seavox_v19.1",
                "properties": {"mrgid_sr": "24074"},
                "geometry": geometry,
            }
        ],
    }
    rich = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "seavox_v19.1",
                "properties": {"mrgid_sr": "24074", "mrgid_r": "23620"},
                "geometry": geometry,
            }
        ],
    }
    sparse_path = tmp_path / "sparse.geojson"
    rich_path = tmp_path / "rich.geojson"
    sparse_path.write_text(json.dumps(sparse), encoding="utf-8")
    rich_path.write_text(json.dumps(rich), encoding="utf-8")

    features = _load_seavox([sparse_path, rich_path])

    assert len(features) == 1
    assert features[0]["properties"] == {"mrgid_sr": "24074", "mrgid_r": "23620"}


def test_lookup_artifact_is_reproducible_and_indexed(tmp_path: Path) -> None:
    source = tmp_path / "regions.geojson"
    source.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "test", "kind": "area"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [0.0, 0.0]]
                            ],
                        },
                    }
                ],
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    geometry_path = tmp_path / "regions.lookup.wkb"
    index_path = tmp_path / "regions.lookup.json"

    geometry_sha256, index_sha256 = build_lookup_artifact(
        source, geometry_path, index_path
    )
    index = json.loads(index_path.read_text(encoding="utf-8"))
    record = index["features"][0]
    geometry = from_wkb(
        geometry_path.read_bytes()[
            record["offset"] : record["offset"] + record["length"]
        ]
    )

    assert len(geometry_sha256) == len(index_sha256) == 64
    assert index["source_sha256"]
    assert record["bounds"] == [0.0, 0.0, 2.0, 1.0]
    assert geometry.geom_type == "Polygon"
