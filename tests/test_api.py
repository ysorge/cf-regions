from __future__ import annotations

import math

import pytest
from shapely.geometry import shape

import cfregions
from cfregions import (
    CFVersionNotFoundError,
    CoordinateError,
    RegionNotFoundError,
    SpatialProfileNotFoundError,
)


def names_at(longitude: float, latitude: float) -> set[str]:
    return set(cfregions.match_region_names(longitude=longitude, latitude=latitude))


def test_catalog_contains_every_cf_v5_name() -> None:
    names = cfregions.list_region_names()

    assert len(names) == 74
    assert names == tuple(sorted(names))
    assert "africa" in names
    assert "yellow_sea" in names


def test_land_lookup_returns_nested_and_global_regions() -> None:
    names = names_at(13.405, 52.52)

    assert {"europe", "eurasia", "global_land", "northern_hemisphere", "global"} <= names
    assert "global_ocean" not in names


def test_ancestor_expansion_can_be_disabled() -> None:
    matches = cfregions.match_regions(
        longitude=5.0,
        latitude=56.0,
        include_ancestors=False,
    )

    assert matches
    assert all(match.relation != "ancestor" for match in matches)
    assert "north_sea" in {match.name for match in matches}


def test_include_ancestors_must_be_boolean() -> None:
    with pytest.raises(CoordinateError, match="include_ancestors"):
        cfregions.match_regions(  # type: ignore[arg-type]
            longitude=5.0,
            latitude=56.0,
            include_ancestors="yes",
        )


def test_hierarchy_edges_distinguish_gcmd_projection_and_curation() -> None:
    edges = cfregions.list_hierarchy_edges(region_name="north_sea")
    by_pair = {(edge.child, edge.parent): edge for edge in edges}

    gcmd = by_pair[("north_sea", "atlantic_ocean")]
    assert gcmd.origin == "gcmd_path_projection"
    assert gcmd.source.name == "NASA GCMD Location Keywords"
    assert gcmd.source_path[-1] == "NORTH SEA"

    curated = by_pair[("atlantic_ocean", "global_ocean")]
    assert curated.origin == "mapping_curation"
    assert curated.source_path == ()
    assert curated.mapping.id == "cfregions-default"


def test_hierarchy_rejects_unknown_region() -> None:
    with pytest.raises(RegionNotFoundError, match="unknown CF standardized region"):
        cfregions.list_hierarchy_edges(region_name="not_a_cf_region")


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ({"lonlat": "7.990654,24.602804"}, (7.990654, 24.602804)),
        ({"lonlat": "7.990654, 24.602804"}, (7.990654, 24.602804)),
        ({"latlon": "24.602804,7.990654"}, (7.990654, 24.602804)),
        ({"latlon": "24.602804, 7.990654"}, (7.990654, 24.602804)),
        ({"lonlat": (7.990654, 24.602804)}, (7.990654, 24.602804)),
    ],
)
def test_combined_coordinate_forms(
    arguments: dict[str, object], expected: tuple[float, float]
) -> None:
    assert cfregions.resolve_coordinates(**arguments) == expected  # type: ignore[arg-type]
    assert cfregions.match_region_names(**arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"longitude": 7.0},
        {"latitude": 24.0},
        {"lonlat": "7,24", "latlon": "24,7"},
        {"longitude": 7.0, "latitude": 24.0, "lonlat": "7,24"},
    ],
)
def test_coordinate_forms_must_be_complete_and_unambiguous(
    arguments: dict[str, object],
) -> None:
    with pytest.raises(CoordinateError):
        cfregions.match_region_names(**arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["7", "7,24,9", "seven,24", "nan,24"])
def test_combined_coordinate_form_rejects_invalid_values(value: str) -> None:
    with pytest.raises(CoordinateError, match="lonlat"):
        cfregions.match_region_names(lonlat=value)


def test_sea_lookup_returns_specific_and_parent_regions() -> None:
    names = names_at(-90.0, 25.0)

    assert {"gulf_of_mexico", "atlantic_ocean", "global_ocean", "global"} <= names
    assert "northern_hemisphere" in names


def test_lake_lookup_connects_to_continent_hierarchy() -> None:
    matches = cfregions.match_regions(longitude=33.0, latitude=-1.0)
    by_name = {match.name: match for match in matches}

    assert "lake_victoria" in by_name
    assert "africa" in by_name
    assert "global_land" in by_name
    assert by_name["lake_victoria"].relation == "covered_by"


def test_section_lines_are_opt_in() -> None:
    default_names = names_at(-155.0, 1.0)
    matches = cfregions.match_regions(
        longitude=-155.0,
        latitude=1.0,
        section_tolerance_km=1.0,
    )
    by_name = {match.name: match for match in matches}

    assert "pacific_equatorial_undercurrent" not in default_names
    assert by_name["pacific_equatorial_undercurrent"].relation == "near_section"
    assert by_name["pacific_equatorial_undercurrent"].distance_km == pytest.approx(0.0)


def test_section_distance_is_spherical_and_respects_tolerance() -> None:
    far = cfregions.match_region_names(
        longitude=-154.0,
        latitude=1.0,
        section_tolerance_km=100.0,
    )
    near = cfregions.match_regions(
        longitude=-154.0,
        latitude=1.0,
        section_tolerance_km=120.0,
    )

    assert "pacific_equatorial_undercurrent" not in far
    match = next(item for item in near if item.name == "pacific_equatorial_undercurrent")
    assert match.distance_km == pytest.approx(111.18, abs=0.5)


@pytest.mark.parametrize(
    ("longitude", "latitude", "message"),
    [
        (181.0, 0.0, "longitude"),
        (0.0, 91.0, "latitude"),
        (math.nan, 0.0, "longitude"),
        (True, 0.0, "longitude"),
    ],
)
def test_invalid_coordinates_raise_clear_errors(
    longitude: object, latitude: object, message: str
) -> None:
    with pytest.raises(CoordinateError, match=message):
        cfregions.match_region_names(  # type: ignore[arg-type]
            longitude=longitude,
            latitude=latitude,
        )


def test_invalid_section_tolerance_is_rejected() -> None:
    with pytest.raises(CoordinateError, match="section_tolerance_km"):
        cfregions.match_region_names(
            longitude=0.0,
            latitude=0.0,
            section_tolerance_km=-1.0,
        )


def test_unknown_region_raises_domain_error() -> None:
    with pytest.raises(RegionNotFoundError, match="unknown CF standardized region"):
        cfregions.get_region(region_name="not_a_cf_region")


def test_shape_is_geojson_and_is_a_defensive_copy() -> None:
    first = cfregions.get_region_shape(region_name="fram_strait")
    first["properties"]["name"] = "changed"
    second = cfregions.get_region_shape(region_name="fram_strait")

    assert second["type"] == "Feature"
    assert second["properties"]["name"] == "fram_strait"
    assert (
        second["properties"]["spatial_profile_id"]
        == "cfregions-default"
    )
    assert second["properties"]["spatial_profile_version"] == "2026.09.1"
    assert second["geometry"]["type"] == "MultiLineString"


def test_dataset_info_is_versioned() -> None:
    info = cfregions.get_dataset_info()

    assert info.cf_version == "5"
    assert info.region_count == 74
    assert info.hierarchy_name == "NASA GCMD Location Keywords"
    assert info.mapping_id == "cfregions-default"
    assert info.mapping_version == "2026.09.1"
    assert info.profile.id == info.mapping_id
    assert info.profile.version == info.mapping_version
    assert info.profile.is_default is True
    assert info.profile.cf_versions == ("1", "2", "3", "4", "5")
    assert info.area_predicate == "covers"
    assert info.boundary_inclusive is True
    assert {item.resolution for item in info.geometry_representations} == {"low", "high"}
    high = next(
        item for item in info.geometry_representations if item.resolution == "high"
    )
    assert high.processing.method == "simplify_and_round"
    assert high.processing.parameters["output_simplification_degrees"] == 0.001
    assert high.processing.parameters["output_simplification_preserves_topology"] is True
    assert info.limitations


def test_bundled_spatial_profile_is_discoverable_and_selectable() -> None:
    profiles = cfregions.list_spatial_profiles()
    selected = cfregions.get_spatial_profile()
    exact = cfregions.get_spatial_profile(
        profile="cfregions-default",
        profile_version="2026.09.1",
    )

    assert profiles == (selected,)
    assert exact == selected
    assert cfregions.list_spatial_profile_ids() == (selected.id,)
    assert cfregions.list_spatial_profile_versions(profile=selected.id) == (
        selected.version,
    )
    assert selected.title == "cfregions default"
    assert "NASA GCMD" in selected.basis
    assert selected.scope
    assert cfregions.match_region_names(
        lonlat="7.990654,24.602804",
        profile=selected.id,
        profile_version=selected.version,
    )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"profile": "missing"}, "unknown spatial interpretation profile"),
        (
            {
                "profile": "cfregions-default",
                "profile_version": "missing",
            },
            "unknown spatial interpretation profile or version",
        ),
    ],
)
def test_unknown_spatial_profile_selection_is_rejected(
    arguments: dict[str, str], message: str
) -> None:
    with pytest.raises(SpatialProfileNotFoundError, match=message):
        cfregions.get_dataset_info(**arguments)


def test_match_preserves_reproducible_mapping_and_source_provenance() -> None:
    direct = next(
        match
        for match in cfregions.match_regions(longitude=13.405, latitude=52.52)
        if match.name == "europe"
    )
    parent = next(
        match
        for match in cfregions.match_regions(
            longitude=0.2981950957576771,
            latitude=70.56625,
        )
        if match.relation == "ancestor"
    )

    assert direct.cf_version == "5"
    assert direct.mapping.id == "cfregions-default"
    assert direct.mapping.geometry_resolution == "low"
    assert direct.method == "polygon_lookup"
    assert direct.predicate == "covers"
    assert direct.source.name == "Natural Earth geography regions"
    assert parent.relation == "ancestor"
    assert parent.method == "hierarchy_expansion"
    assert parent.predicate == "broader"
    assert parent.source.name == "NASA GCMD Location Keywords"
    assert direct.to_dict()["mapping"]["version"] == direct.mapping.version


def test_boundary_lookup_is_inclusive_and_returns_both_hemispheres() -> None:
    matches = cfregions.match_regions(longitude=0.0, latitude=0.0)
    direct_names = {match.name for match in matches if match.relation == "covered_by"}

    assert {"northern_hemisphere", "southern_hemisphere", "global"} <= direct_names


def test_shape_resolution_is_explicit_and_does_not_change_lookup() -> None:
    low = cfregions.get_region_shape(
        region_name="north_sea", geometry_resolution="low"
    )
    high = cfregions.get_region_shape(
        region_name="north_sea", geometry_resolution="high"
    )

    assert low["properties"]["geometry_resolution"] == "low"
    assert high["properties"]["geometry_resolution"] == "high"
    assert len(str(high["geometry"])) > len(str(low["geometry"]))
    first = [
        match.to_dict()
        for match in cfregions.match_regions(longitude=5.0, latitude=56.0)
    ]
    second = [
        match.to_dict()
        for match in cfregions.match_regions(longitude=5.0, latitude=56.0)
    ]
    assert first == second


def test_unknown_shape_resolution_is_rejected() -> None:
    with pytest.raises(cfregions.GeometryResolutionNotFoundError, match="available"):
        cfregions.get_region_shape(
            region_name="north_sea", geometry_resolution="ultra"
        )


@pytest.mark.parametrize("geometry_resolution", ["low", "high"])
def test_north_sea_and_baltic_preserve_source_defined_gap(
    geometry_resolution: str,
) -> None:
    north_sea = shape(
        cfregions.get_region_shape(
            region_name="north_sea",
            geometry_resolution=geometry_resolution,
        )["geometry"]
    )
    baltic_sea = shape(
        cfregions.get_region_shape(
            region_name="baltic_sea",
            geometry_resolution=geometry_resolution,
        )["geometry"]
    )

    assert north_sea.disjoint(baltic_sea)
    assert north_sea.distance(baltic_sea) > 0


def test_every_area_contains_its_representative_point() -> None:
    for region in cfregions.list_regions():
        if region.kind != "area":
            continue
        feature = cfregions.get_region_shape(region_name=region.name)
        representative_point = shape(feature["geometry"]).representative_point()
        matches = cfregions.match_regions(
            longitude=representative_point.x,
            latitude=representative_point.y,
        )
        relations = {match.name: match.relation for match in matches}
        assert relations.get(region.name) == "covered_by", region.name


def test_every_section_matches_an_endpoint_with_positive_tolerance() -> None:
    for region in cfregions.list_regions():
        if region.kind != "section":
            continue
        feature = cfregions.get_region_shape(region_name=region.name)
        geometry = feature["geometry"]
        coordinates = geometry["coordinates"]
        endpoint = coordinates[0] if geometry["type"] == "LineString" else coordinates[0][0]
        matches = cfregions.match_regions(
            longitude=endpoint[0],
            latitude=endpoint[1],
            section_tolerance_km=0.001,
        )
        relations = {match.name: match.relation for match in matches}
        assert relations.get(region.name) == "near_section", region.name


@pytest.mark.parametrize(
    ("version", "count"),
    [("1", 52), ("2", 68), ("3", 70), ("4", 72), ("5", 74), ("current", 74)],
)
def test_every_bundled_cf_version_is_selectable(version: str, count: int) -> None:
    info = cfregions.get_dataset_info(cf_version=version)

    assert info.region_count == count
    assert len(cfregions.list_region_names(cf_version=version)) == count
    assert info.cf_version == ("5" if version == "current" else version)


def test_old_versions_exclude_names_added_later() -> None:
    assert "barents_opening" not in cfregions.list_region_names(cf_version="1")
    assert "barents_opening" in cfregions.list_region_names(cf_version="2")
    assert "northern_hemisphere" not in cfregions.list_region_names(cf_version="4")
    assert "northern_hemisphere" in cfregions.list_region_names(cf_version="5")


def test_unknown_cf_version_raises_domain_error() -> None:
    with pytest.raises(CFVersionNotFoundError, match="available versions"):
        cfregions.get_dataset_info(cf_version="99")
