from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from pathlib import Path

import pytest
from tools.lookup_artifact import build_lookup_artifact

import cfregions


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _external_dataset(root: Path, *, profile_checksums: bool = True) -> Path:
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
    representation = {
        "label": "Low detail",
        "description": "Test geometry.",
        "geometry_file": "geometry/low.geojson",
        "feature_count": 1,
        "processing": {
            "method": "test",
            "parameters": {"coordinate_precision_degrees": 0.000001},
        },
    }
    hierarchy_metadata = {
        "name": "Test hierarchy",
        "version": "1",
        "date": "2099-01-01",
        "url": "https://example.test/hierarchy",
        "hierarchy_file": "hierarchy.json",
        "edge_count": 0,
    }
    if profile_checksums:
        representation["sha256"] = _sha256(geometry)
        hierarchy_metadata["sha256"] = _sha256(hierarchy)
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
                "low": representation
            },
            "hierarchy": hierarchy_metadata,
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


def test_profile_checksums_are_optional(tmp_path: Path) -> None:
    _external_dataset(tmp_path, profile_checksums=False)

    info = cfregions.get_dataset_info(data_directory=tmp_path)
    match = cfregions.match_regions(
        longitude=0,
        latitude=0,
        data_directory=tmp_path,
    )[0]

    assert info.lookup_geometry_sha256 is None
    assert info.geometry_representations[0].sha256 is None
    assert match.mapping.geometry_sha256 is None


def test_declared_profile_geometry_checksum_is_verified(tmp_path: Path) -> None:
    _external_dataset(tmp_path)
    geometry = tmp_path / "profiles/test-profile/1/geometry/low.geojson"
    geometry.write_text("{}", encoding="utf-8")

    # Metadata discovery intentionally does not open a potentially large geometry file.
    assert cfregions.get_dataset_info(data_directory=tmp_path).profile.id == "test-profile"
    with pytest.raises(cfregions.RegionDataError, match="checksum mismatch"):
        cfregions.match_regions(
            longitude=0,
            latitude=0,
            data_directory=tmp_path,
        )


def test_optional_lookup_artifact_is_used_and_verified(tmp_path: Path) -> None:
    _external_dataset(tmp_path)
    profile_root = tmp_path / "profiles/test-profile/1"
    geometry = profile_root / "geometry/low.geojson"
    pack = profile_root / "geometry/low.lookup.wkb"
    index = profile_root / "geometry/low.lookup.json"
    pack_sha256, index_sha256 = build_lookup_artifact(geometry, pack, index)
    manifest_path = profile_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["representations"]["low"]["lookup_artifact"] = {
        "format": "wkb-pack-v1",
        "geometry_file": "geometry/low.lookup.wkb",
        "index_file": "geometry/low.lookup.json",
        "sha256": pack_sha256,
        "index_sha256": index_sha256,
    }
    _write_json(manifest_path, manifest)

    assert cfregions.match_region_names(
        longitude=0,
        latitude=0,
        data_directory=tmp_path,
    ) == ("global",)

    tampered_root = tmp_path / "tampered"
    _external_dataset(tampered_root)
    tampered_profile = tampered_root / "profiles/test-profile/1"
    tampered_geometry = tampered_profile / "geometry/low.geojson"
    tampered_pack = tampered_profile / "geometry/low.lookup.wkb"
    tampered_index = tampered_profile / "geometry/low.lookup.json"
    pack_sha256, index_sha256 = build_lookup_artifact(
        tampered_geometry, tampered_pack, tampered_index
    )
    tampered_manifest_path = tampered_profile / "manifest.json"
    tampered_manifest = json.loads(tampered_manifest_path.read_text(encoding="utf-8"))
    tampered_manifest["representations"]["low"]["lookup_artifact"] = {
        "format": "wkb-pack-v1",
        "geometry_file": "geometry/low.lookup.wkb",
        "index_file": "geometry/low.lookup.json",
        "sha256": pack_sha256,
        "index_sha256": index_sha256,
    }
    _write_json(tampered_manifest_path, tampered_manifest)
    tampered_pack.write_bytes(tampered_pack.read_bytes() + b"tampered")

    with pytest.raises(cfregions.RegionDataError, match="checksum mismatch"):
        cfregions.match_regions(
            longitude=0,
            latitude=0,
            data_directory=tampered_root,
        )


@pytest.mark.parametrize(
    ("missing_field", "message"),
    [
        ("source_sha256", "representation with lookup_artifact must declare sha256"),
        ("artifact_sha256", "lookup_artifact must declare sha256 and index_sha256"),
        ("index_sha256", "lookup_artifact must declare sha256 and index_sha256"),
    ],
)
def test_lookup_artifact_requires_complete_checksum_binding(
    tmp_path: Path,
    missing_field: str,
    message: str,
) -> None:
    _external_dataset(tmp_path, profile_checksums=False)
    manifest_path = tmp_path / "profiles/test-profile/1/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    representation = manifest["representations"]["low"]
    representation["sha256"] = "0" * 64
    artifact = {
        "format": "wkb-pack-v1",
        "geometry_file": "geometry/low.lookup.wkb",
        "index_file": "geometry/low.lookup.json",
        "sha256": "1" * 64,
        "index_sha256": "2" * 64,
    }
    representation["lookup_artifact"] = artifact
    if missing_field == "source_sha256":
        del representation["sha256"]
    elif missing_field == "artifact_sha256":
        del artifact["sha256"]
    else:
        del artifact["index_sha256"]
    _write_json(manifest_path, manifest)

    with pytest.raises(cfregions.RegionDataError, match=message):
        cfregions.get_dataset_info(data_directory=tmp_path)


def test_lookup_artifact_index_must_name_its_exact_geojson_source(
    tmp_path: Path,
) -> None:
    _external_dataset(tmp_path)
    profile_root = tmp_path / "profiles/test-profile/1"
    geometry = profile_root / "geometry/low.geojson"
    pack = profile_root / "geometry/low.lookup.wkb"
    index_path = profile_root / "geometry/low.lookup.json"
    pack_sha256, _ = build_lookup_artifact(geometry, pack, index_path)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["source_sha256"] = "0" * 64
    _write_json(index_path, index)
    manifest_path = profile_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["representations"]["low"]["lookup_artifact"] = {
        "format": "wkb-pack-v1",
        "geometry_file": "geometry/low.lookup.wkb",
        "index_file": "geometry/low.lookup.json",
        "sha256": pack_sha256,
        "index_sha256": _sha256(index_path),
    }
    _write_json(manifest_path, manifest)

    with pytest.raises(cfregions.RegionDataError, match="does not match its GeoJSON"):
        cfregions.match_regions(
            longitude=0,
            latitude=0,
            data_directory=tmp_path,
        )


def test_declared_profile_checksum_must_be_a_sha256_digest(tmp_path: Path) -> None:
    _external_dataset(tmp_path, profile_checksums=False)
    manifest_path = tmp_path / "profiles/test-profile/1/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["representations"]["low"]["sha256"] = None
    _write_json(manifest_path, manifest)

    with pytest.raises(cfregions.RegionDataError, match="lowercase SHA-256"):
        cfregions.get_dataset_info(data_directory=tmp_path)


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
