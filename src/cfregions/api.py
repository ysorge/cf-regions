"""Small, version-aware public Python API shared by all applications."""

from __future__ import annotations

from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import Any

from .catalog import CoordinatePair, RegionCatalog, resolve_coordinates
from .datasets import CFRegistry
from .errors import SpatialProfileNotFoundError
from .models import (
    DatasetInfo,
    HierarchyEdge,
    Region,
    RegionMatch,
    SpatialInterpretationProfile,
)
from .profiles import DirectorySpatialProfileProvider, SpatialProfileResolver

DataDirectory = str | Path | None
ProfileDirectories = Sequence[str | Path] | None


def _directory_key(data_directory: DataDirectory) -> str | None:
    if data_directory is None:
        return None
    return str(Path(data_directory).expanduser().resolve())


def _profile_directory_keys(
    profile_directories: ProfileDirectories,
) -> tuple[str, ...]:
    if profile_directories is None:
        return ()
    return tuple(
        str(Path(directory).expanduser().resolve())
        for directory in profile_directories
    )


@cache
def _profile_resolver(
    data_directory: str | None = None,
    profile_directories: tuple[str, ...] = (),
) -> SpatialProfileResolver:
    primary = (
        DirectorySpatialProfileProvider.bundled()
        if data_directory is None
        else DirectorySpatialProfileProvider.from_data_directory(data_directory)
    )
    additional = tuple(
        DirectorySpatialProfileProvider.from_profile_directory(directory)
        for directory in profile_directories
    )
    return SpatialProfileResolver((primary, *additional))


@cache
def _cf_registry(data_directory: str | None = None) -> CFRegistry:
    return (
        CFRegistry.bundled()
        if data_directory is None
        else CFRegistry.from_directory(data_directory)
    )


@cache
def _catalog(
    cf_version: str,
    profile: str,
    profile_version: str,
    data_directory: str | None,
    profile_directories: tuple[str, ...],
) -> RegionCatalog:
    resolved_profile = _profile_resolver(data_directory, profile_directories).resolve(
        profile, profile_version
    )
    return RegionCatalog.from_sources(
        _cf_registry(data_directory),
        resolved_profile.dataset,
        cf_version=cf_version,
    )


def get_catalog(
    *,
    cf_version: str = "current",
    profile: str = "default",
    profile_version: str = "current",
    data_directory: DataDirectory = None,
    profile_directories: ProfileDirectories = None,
) -> RegionCatalog:
    """Return a cached catalog for a CF release and spatial profile."""

    return _catalog(
        str(cf_version),
        str(profile),
        str(profile_version),
        _directory_key(data_directory),
        _profile_directory_keys(profile_directories),
    )


def list_spatial_profiles(
    *,
    data_directory: DataDirectory = None,
    profile_directories: ProfileDirectories = None,
) -> tuple[SpatialInterpretationProfile, ...]:
    """Return built-in and additionally discovered spatial profiles."""

    return _profile_resolver(
        _directory_key(data_directory),
        _profile_directory_keys(profile_directories),
    ).list_profiles()


def list_spatial_profile_ids(
    *,
    data_directory: DataDirectory = None,
    profile_directories: ProfileDirectories = None,
) -> tuple[str, ...]:
    """Return the stable IDs of all available spatial profiles."""

    return tuple(
        sorted(
            {
                item.id
                for item in list_spatial_profiles(
                    data_directory=data_directory,
                    profile_directories=profile_directories,
                )
            }
        )
    )


def list_spatial_profile_versions(
    *,
    profile: str = "default",
    data_directory: DataDirectory = None,
    profile_directories: ProfileDirectories = None,
) -> tuple[str, ...]:
    """Return all available versions for one profile ID or alias."""

    directory = _directory_key(data_directory)
    resolver = _profile_resolver(
        directory,
        _profile_directory_keys(profile_directories),
    )
    requested = str(profile).strip()
    resolved_id = (
        resolver.resolve("default", "current").info.id
        if requested == "default"
        else requested
    )
    versions = tuple(
        sorted(
            item.version
            for item in resolver.list_profiles()
            if item.id == resolved_id
        )
    )
    if not versions:
        available = ", ".join(
            sorted({item.id for item in resolver.list_profiles()})
        )
        raise SpatialProfileNotFoundError(
            f"unknown spatial interpretation profile {requested!r}; "
            f"available profiles: {available}"
        )
    return versions


def get_spatial_profile(
    *,
    profile: str = "default",
    profile_version: str = "current",
    data_directory: DataDirectory = None,
    profile_directories: ProfileDirectories = None,
) -> SpatialInterpretationProfile:
    """Resolve and return one spatial interpretation profile."""

    return _profile_resolver(
        _directory_key(data_directory),
        _profile_directory_keys(profile_directories),
    ).resolve(
        profile, profile_version
    ).info


def list_cf_versions(
    *,
    data_directory: DataDirectory = None,
) -> tuple[str, ...]:
    """Return CF releases independently of any spatial-profile selection."""

    return _cf_registry(_directory_key(data_directory)).list_versions()


def match_region_names(
    *,
    longitude: float | None = None,
    latitude: float | None = None,
    lonlat: CoordinatePair | None = None,
    latlon: CoordinatePair | None = None,
    section_tolerance_km: float = 0.0,
    include_ancestors: bool = True,
    cf_version: str = "current",
    profile: str = "default",
    profile_version: str = "current",
    data_directory: DataDirectory = None,
    profile_directories: ProfileDirectories = None,
) -> tuple[str, ...]:
    """Return names only, ordered specific to broad; use ``match_regions`` for provenance."""

    return tuple(
        match.name
        for match in match_regions(
            longitude=longitude,
            latitude=latitude,
            lonlat=lonlat,
            latlon=latlon,
            section_tolerance_km=section_tolerance_km,
            include_ancestors=include_ancestors,
            cf_version=cf_version,
            profile=profile,
            profile_version=profile_version,
            data_directory=data_directory,
            profile_directories=profile_directories,
        )
    )


def match_regions(
    *,
    longitude: float | None = None,
    latitude: float | None = None,
    lonlat: CoordinatePair | None = None,
    latlon: CoordinatePair | None = None,
    section_tolerance_km: float = 0.0,
    include_ancestors: bool = True,
    cf_version: str = "current",
    profile: str = "default",
    profile_version: str = "current",
    data_directory: DataDirectory = None,
    profile_directories: ProfileDirectories = None,
) -> tuple[RegionMatch, ...]:
    """Return detailed direct and hierarchical matches for a point."""

    resolved_longitude, resolved_latitude = resolve_coordinates(
        longitude=longitude,
        latitude=latitude,
        lonlat=lonlat,
        latlon=latlon,
    )
    return get_catalog(
        cf_version=cf_version,
        profile=profile,
        profile_version=profile_version,
        data_directory=data_directory,
        profile_directories=profile_directories,
    ).match(
        longitude=resolved_longitude,
        latitude=resolved_latitude,
        section_tolerance_km=section_tolerance_km,
        include_ancestors=include_ancestors,
    )


def list_hierarchy_edges(
    *,
    region_name: str | None = None,
    cf_version: str = "current",
    profile: str = "default",
    profile_version: str = "current",
    data_directory: DataDirectory = None,
    profile_directories: ProfileDirectories = None,
) -> tuple[HierarchyEdge, ...]:
    """Return the full mapping hierarchy or one region's ancestor subgraph."""

    return get_catalog(
        cf_version=cf_version,
        profile=profile,
        profile_version=profile_version,
        data_directory=data_directory,
        profile_directories=profile_directories,
    ).list_hierarchy_edges(region_name)


def list_regions(
    *,
    cf_version: str = "current",
    profile: str = "default",
    profile_version: str = "current",
    data_directory: DataDirectory = None,
    profile_directories: ProfileDirectories = None,
) -> tuple[Region, ...]:
    """Return metadata for one CF release in alphabetical order."""

    return get_catalog(
        cf_version=cf_version,
        profile=profile,
        profile_version=profile_version,
        data_directory=data_directory,
        profile_directories=profile_directories,
    ).list_regions()


def list_region_names(
    *,
    cf_version: str = "current",
    profile: str = "default",
    profile_version: str = "current",
    data_directory: DataDirectory = None,
    profile_directories: ProfileDirectories = None,
) -> tuple[str, ...]:
    """Return all standardized names in one CF release."""

    return tuple(
        region.name
        for region in list_regions(
            cf_version=cf_version,
            profile=profile,
            profile_version=profile_version,
            data_directory=data_directory,
            profile_directories=profile_directories,
        )
    )


def get_region(
    *,
    region_name: str,
    cf_version: str = "current",
    profile: str = "default",
    profile_version: str = "current",
    data_directory: DataDirectory = None,
    profile_directories: ProfileDirectories = None,
) -> Region:
    """Return metadata for one exact standardized name."""

    return get_catalog(
        cf_version=cf_version,
        profile=profile,
        profile_version=profile_version,
        data_directory=data_directory,
        profile_directories=profile_directories,
    ).get_region(region_name)


def get_region_shape(
    *,
    region_name: str,
    geometry_resolution: str | None = None,
    cf_version: str = "current",
    profile: str = "default",
    profile_version: str = "current",
    data_directory: DataDirectory = None,
    profile_directories: ProfileDirectories = None,
) -> dict[str, Any]:
    """Return one interpreted GeoJSON Feature in WGS84 at a declared resolution."""

    return get_catalog(
        cf_version=cf_version,
        profile=profile,
        profile_version=profile_version,
        data_directory=data_directory,
        profile_directories=profile_directories,
    ).get_region_shape(region_name, geometry_resolution=geometry_resolution)


def get_dataset_info(
    *,
    cf_version: str = "current",
    profile: str = "default",
    profile_version: str = "current",
    data_directory: DataDirectory = None,
    profile_directories: ProfileDirectories = None,
) -> DatasetInfo:
    """Return CF-vocabulary and geometry-edition provenance metadata."""

    return get_catalog(
        cf_version=cf_version,
        profile=profile,
        profile_version=profile_version,
        data_directory=data_directory,
        profile_directories=profile_directories,
    ).dataset_info
