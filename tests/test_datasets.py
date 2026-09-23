from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from pathlib import Path

import pytest

import cfregions


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _external_dataset(root: Path) -> Path:
    vocabulary = root / "vocabularies/standardized-region-list.9.xml"
    vocabulary.parent.mkdir(parents=True)
    vocabulary.write_text(
        """<?xml version="1.0"?>
<standardized_region_list>
  <version_number>9</version_number>
  <date>1 January 2099</date>
  <entry id="global"><description>Earth.</description></entry>
</standardized_region_list>
""",
        encoding="utf-8",
    )
    geometry = root / "profiles/test-profile/1/geometry/low.geojson"
    feature = {
        "type": "Feature",
        "id": "global",
        "properties": {
            "name": "global",
            "kind": "area",
            "nvs_concept_url": "https://example.test/global",
            "geometry_source": "Test",
            "geometry_source_url": "https://example.test/data",
            "geometry_source_version": "1",
            "geometry_license": "CC0",
            "geometry_method": "test fixture",
            "geometry_contexts": [],
            "specificity": 0,
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-180, -90], [180, -90], [180, 90], [-180, 90], [-180, -90]]],
        },
    }
    _write_json(geometry, {"type": "FeatureCollection", "features": [feature]})
    hierarchy = root / "profiles/test-profile/1/hierarchy.json"
    _write_json(
        hierarchy,
        {
            "schema_version": 1,
            "edges": [],
        },
    )
    _write_json(
        root / "profiles/test-profile/1/manifest.json",
        {
            "schema_version": 1,
            "profile": {
                "id": "test-profile",
                "version": "1",
                "title": "Test profile",
                "description": "Test spatial interpretation.",
                "basis": "Synthetic test geometry and hierarchy.",
                "scope": "Tests only.",
                "license": "CC0",
                "homepage": "https://example.test/profile",
            },
            "supported_cf_versions": ["9"],
            "generated_on": "2099-01-01",
            "crs": "OGC:CRS84",
            "lookup": {
                "behavior_version": "1",
                "geometry_resolution": "low",
                "default_geometry_resolution": "low",
                "area_predicate": "covers",
                "boundary_inclusive": True,
                "section_method": "minor_great_circle_distance",
            },
            "representations": {
                "low": {
                    "label": "Low detail",
                    "description": "Test geometry.",
                    "geometry_file": "geometry/low.geojson",
                    "sha256": _sha256(geometry),
                    "feature_count": 1,
                    "processing": {
                        "method": "test",
                        "parameters": {"coordinate_precision_degrees": 0.000001},
                    },
                }
            },
            "hierarchy": {
                "name": "Test hierarchy",
                "version": "1",
                "date": "2099-01-01",
                "url": "https://example.test/hierarchy",
                "hierarchy_file": "hierarchy.json",
                "sha256": _sha256(hierarchy),
                "edge_count": 0,
            },
            "sources": [{"name": "Test"}],
            "limitations": ["Test data."],
        },
    )
    _write_json(
        root / "versions/9.json",
        {
            "schema_version": 1,
            "dataset_id": "test-v9",
            "region_count": 1,
            "cf": {
                "version": "9",
                "date": "1 January 2099",
                "url": "https://example.test/cf-v9",
                "vocabulary_file": "vocabularies/standardized-region-list.9.xml",
                "sha256": _sha256(vocabulary),
            },
        },
    )
    _write_json(
        root / "catalog.json",
        {
            "schema_version": 1,
            "default_version": "9",
            "aliases": {"current": "9"},
            "versions": {"9": "versions/9.json"},
        },
    )
    _write_json(
        root / "profile-settings.json",
        {
            "schema_version": 1,
            "default_profile": {"id": "test-profile", "version": "1"},
        },
    )
    return vocabulary


def test_external_self_describing_dataset_is_supported(tmp_path: Path) -> None:
    _external_dataset(tmp_path)

    info = cfregions.get_dataset_info(data_directory=tmp_path)
    names = cfregions.match_region_names(
        longitude=0,
        latitude=0,
        data_directory=tmp_path,
    )

    assert info.dataset_id == "test-v9__test-profile-1"
    assert info.cf_version == "9"
    assert info.profile.id == "test-profile"
    assert info.profile.version == "1"
    assert names == ("global",)
    assert cfregions.get_region(
        region_name="global",
        data_directory=tmp_path,
    ).description == "Earth."


def test_external_dataset_checksum_is_verified(tmp_path: Path) -> None:
    vocabulary = _external_dataset(tmp_path)
    vocabulary.write_text("tampered", encoding="utf-8")

    with pytest.raises(cfregions.RegionDataError, match="checksum mismatch"):
        cfregions.CFRegistry.from_directory(tmp_path).load()


def test_unsupported_catalog_schema_is_rejected(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "catalog.json",
        {
            "schema_version": 99,
            "default_version": "1",
            "aliases": {"current": "1"},
            "versions": {"1": "versions/1.json"},
        },
    )

    with pytest.raises(cfregions.RegionDataError, match=r"unsupported.*schema version"):
        cfregions.CFRegistry.from_directory(tmp_path)


def test_external_data_root_can_select_its_declarative_profile(
    tmp_path: Path,
) -> None:
    _external_dataset(tmp_path)

    info = cfregions.get_dataset_info(
        profile="test-profile",
        profile_version="1",
        data_directory=tmp_path,
    )

    assert info.cf_version == "9"
    assert info.profile.id == "test-profile"


def test_profile_identity_can_change_without_renaming_its_directory(
    tmp_path: Path,
) -> None:
    _external_dataset(tmp_path)
    manifest_path = tmp_path / "profiles/test-profile/1/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["profile"]["id"] = "renamed-profile"
    _write_json(manifest_path, manifest)
    _write_json(
        tmp_path / "profile-settings.json",
        {
            "schema_version": 1,
            "default_profile": {"id": "renamed-profile", "version": "1"},
        },
    )

    info = cfregions.get_dataset_info(data_directory=tmp_path)

    assert info.profile.id == "renamed-profile"


def test_default_selection_reports_stale_profile_identity(tmp_path: Path) -> None:
    _external_dataset(tmp_path)
    manifest_path = tmp_path / "profiles/test-profile/1/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["profile"]["id"] = "renamed-profile"
    _write_json(manifest_path, manifest)

    with pytest.raises(
        cfregions.RegionDataError,
        match="update the default selection when renaming",
    ):
        cfregions.get_dataset_info(data_directory=tmp_path)


def test_profile_directory_adds_discovered_profiles_without_replacing_default(
    tmp_path: Path,
) -> None:
    _external_dataset(tmp_path)

    profiles = cfregions.list_spatial_profiles(
        profile_directories=[tmp_path / "profiles"]
    )
    selected = cfregions.get_spatial_profile()
    additional = cfregions.get_spatial_profile(
        profile="test-profile",
        profile_version="1",
        profile_directories=[tmp_path / "profiles"],
    )

    assert {(item.id, item.version) for item in profiles} == {
        ("cfregions-default", "2026.09.1"),
        ("test-profile", "1"),
    }
    assert selected.id == "cfregions-default"
    assert selected.is_default is True
    assert additional.id == "test-profile"
    assert additional.is_default is False


def test_duplicate_profile_id_and_version_across_directories_is_rejected(
    tmp_path: Path,
) -> None:
    _external_dataset(tmp_path)
    directory = tmp_path / "profiles"

    with pytest.raises(cfregions.RegionDataError, match="duplicate spatial"):
        cfregions.list_spatial_profiles(
            profile_directories=[directory, directory]
        )


def test_cf_registry_loads_without_selecting_a_spatial_profile() -> None:
    release = cfregions.CFRegistry.bundled().load("5")

    assert release.version == "5"
    assert release.dataset_id == "cf-standardized-region-list-v5"
    assert len(release.descriptions) == 74


def test_bundled_cf_manifests_do_not_reference_profile_data() -> None:
    data_root = files("cfregions").joinpath("data")

    for version in cfregions.list_cf_versions():
        manifest = json.loads(
            data_root.joinpath("versions").joinpath(f"{version}.json").read_bytes()
        )
        assert "geometry_manifest" not in manifest
        assert set(manifest) == {"$schema", "schema_version", "dataset_id", "region_count", "cf"}


def test_profile_geometry_and_hierarchy_are_separate_resources() -> None:
    data_root = files("cfregions").joinpath("data")
    base = (
        data_root.joinpath("profiles")
        .joinpath("cfregions-default")
        .joinpath("2026.09.1")
    )
    geometry = json.loads(
        base.joinpath("geometry").joinpath("low.geojson").read_bytes()
    )
    hierarchy = json.loads(base.joinpath("hierarchy.json").read_bytes())

    assert hierarchy["edges"]
    for feature in geometry["features"]:
        assert "parents" not in feature["properties"]
        assert "hierarchy_path" not in feature["properties"]
        assert "description" not in feature["properties"]


def test_profile_discovery_settings_only_select_the_default() -> None:
    data_root = files("cfregions").joinpath("data")
    settings = json.loads(data_root.joinpath("profile-settings.json").read_bytes())

    assert set(settings) == {"$schema", "schema_version", "default_profile"}
    assert settings["default_profile"] == {
        "id": "cfregions-default",
        "version": "2026.09.1",
    }
