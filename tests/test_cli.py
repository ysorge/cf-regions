from __future__ import annotations

import json
from pathlib import Path

import pytest
from shapely import from_wkb, from_wkt

from cfregions.cli import main


def test_lookup_json(capsys: pytest.CaptureFixture[str]) -> None:
    status = main(
        [
            "lookup",
            "--longitude",
            "13.405",
            "--latitude",
            "52.52",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert status == 0
    assert payload["longitude"] == 13.405
    assert payload["cf_version"] == "5"
    assert payload["profile"]["id"] == "cfregions-default"
    assert "europe" in {match["name"] for match in payload["matches"]}


def test_lookup_defaults_to_one_name_per_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["lookup", "--longitude", "13.405", "--latitude", "52.52"]) == 0

    names = capsys.readouterr().out.splitlines()
    assert "europe" in names
    assert "global" in names
    assert all("\t" not in name for name in names)


def test_lookup_table_is_concise(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(
            [
                "lookup",
                "--longitude",
                "13.405",
                "--latitude",
                "52.52",
                "--format",
                "table",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "Region" in output
    assert "Relation" in output
    assert "europe" in output
    assert "covered_by" in output
    assert "cfregions-default" not in output


def test_lookup_jsonl_contains_one_complete_match_per_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "lookup",
                "--longitude",
                "13.405",
                "--latitude",
                "52.52",
                "--format",
                "jsonl",
            ]
        )
        == 0
    )

    matches = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    europe = next(match for match in matches if match["name"] == "europe")
    assert europe["relation"] == "covered_by"
    assert europe["mapping"]["id"] == "cfregions-default"


def test_lookup_can_exclude_hierarchy_ancestors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "lookup",
                "--longitude",
                "5",
                "--latitude",
                "56",
                "--no-ancestors",
                "--format",
                "jsonl",
            ]
        )
        == 0
    )

    matches = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert matches
    assert all(match["relation"] != "ancestor" for match in matches)


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--lonlat", "7.990654,24.602804"),
        ("--lonlat", "7.990654, 24.602804"),
        ("--latlon", "24.602804,7.990654"),
        ("--latlon", "24.602804, 7.990654"),
        ("--lonlat", "-7.990654,24.602804"),
    ],
)
def test_lookup_accepts_combined_coordinates(
    option: str,
    value: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["lookup", option, value, "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    expected_longitude = -7.990654 if value.startswith("-") else 7.990654
    assert payload["longitude"] == pytest.approx(expected_longitude)
    assert payload["latitude"] == pytest.approx(24.602804)


@pytest.mark.parametrize(
    "arguments",
    [
        ["--longitude", "7", "--latitude", "24", "--lonlat", "7,24"],
        ["--lonlat", "7,24", "--latlon", "24,7"],
    ],
)
def test_lookup_rejects_ambiguous_coordinate_forms(
    arguments: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["lookup", *arguments])

    assert error.value.code == 2
    assert "coordinate arguments are ambiguous" in capsys.readouterr().err


def test_lookup_rejects_incomplete_separate_coordinates(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["lookup", "--longitude", "7"])

    assert error.value.code == 2
    assert "longitude and latitude must be provided together" in capsys.readouterr().err


def test_regions_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["regions", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert len(payload) == 74
    assert payload[0]["name"] == "africa"


def test_regions_defaults_to_one_name_per_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["regions"]) == 0
    names = capsys.readouterr().out.splitlines()

    assert len(names) == 74
    assert names[0] == "africa"
    assert all("\t" not in name for name in names)


def test_shape_can_be_written_to_file(tmp_path: Path) -> None:
    output = tmp_path / "africa.geojson"

    assert main(["shape", "africa", "--output", str(output)]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["properties"]["name"] == "africa"


def test_shape_can_be_written_as_wkt(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["shape", "north_sea", "--format", "wkt"]) == 0

    geometry = from_wkt(capsys.readouterr().out.strip())
    assert geometry.geom_type == "MultiPolygon"
    assert not geometry.is_empty


def test_shape_can_be_written_as_hexadecimal_wkb(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["shape", "fram_strait", "--format", "wkb-hex"]) == 0

    geometry = from_wkb(bytes.fromhex(capsys.readouterr().out.strip()))
    assert geometry.geom_type == "MultiLineString"
    assert not geometry.is_empty


def test_shape_can_be_written_as_binary_wkb(tmp_path: Path) -> None:
    output = tmp_path / "north-sea.wkb"
    assert (
        main(["shape", "north_sea", "--format", "wkb", "--output", str(output)])
        == 0
    )

    geometry = from_wkb(output.read_bytes())
    assert geometry.geom_type == "MultiPolygon"
    assert not geometry.is_empty


def test_hierarchy_tree_shows_edge_origins(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["hierarchy", "north_sea"]) == 0
    output = capsys.readouterr().out

    assert "north_sea" in output
    assert "atlantic_ocean [GCMD]" in output
    assert "global_ocean [curated]" in output


def test_hierarchy_json_is_a_provenance_rich_graph(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["hierarchy", "north_sea", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["region_name"] == "north_sea"
    assert payload["hierarchy"]["name"] == "NASA GCMD Location Keywords"
    assert payload["count"] == len(payload["edges"])
    assert {
        (edge["child"], edge["parent"], edge["origin"])
        for edge in payload["edges"]
    } >= {
        ("north_sea", "atlantic_ocean", "gcmd_path_projection"),
        ("atlantic_ocean", "global_ocean", "mapping_curation"),
    }


def test_info_text(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["info"]) == 0

    output = capsys.readouterr().out
    assert "CF Standardized Region List: 5" in output
    assert "Regions: 74" in output


def test_historical_version_can_be_selected(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["regions", "--cf-version", "1", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert len(payload) == 52
    assert "barents_opening" not in {region["name"] for region in payload}


def test_versions_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["versions"]) == 0
    assert capsys.readouterr().out.splitlines() == ["1", "2", "3", "4", "5"]


def test_profiles_command_lists_bundled_profile(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["profiles"]) == 0
    output = capsys.readouterr().out

    assert "cfregions-default" in output
    assert "2026.09.1" in output
    assert "1, 2, 3, 4, 5" in output


def test_profile_can_be_selected_explicitly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "info",
                "--profile",
                "cfregions-default",
                "--profile-version",
                "2026.09.1",
                "--format",
                "json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["profile"]["id"] == "cfregions-default"
    assert payload["profile"]["version"] == "2026.09.1"


def test_cli_reports_domain_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(["lookup", "--longitude", "999", "--latitude", "0"])

    assert error.value.code == 2
    assert "longitude must be between" in capsys.readouterr().err
