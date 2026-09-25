"""Spatial interpretation profile discovery and selection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Protocol

from .datasets import Resource, SpatialProfileDataset
from .errors import RegionDataError, SpatialProfileNotFoundError
from .models import SpatialInterpretationProfile


@dataclass(frozen=True, slots=True)
class ResolvedSpatialProfile:
    """A selected profile together with its own profile-dependent resources."""

    info: SpatialInterpretationProfile
    dataset: SpatialProfileDataset


class SpatialProfileProvider(Protocol):
    """Contract future bundled, directory, or entry-point providers implement."""

    def list_profiles(self) -> tuple[SpatialInterpretationProfile, ...]: ...

    def resolve(
        self,
        profile: str = "default",
        profile_version: str = "current",
    ) -> ResolvedSpatialProfile: ...


class SpatialProfileResolver:
    """Combine profile providers behind one deterministic selection interface."""

    def __init__(self, providers: tuple[SpatialProfileProvider, ...]) -> None:
        if not providers:
            raise RegionDataError("at least one spatial profile provider is required")
        self._providers = providers

    def list_profiles(self) -> tuple[SpatialInterpretationProfile, ...]:
        """Return profiles from all providers and reject duplicate identities."""

        by_identity: dict[tuple[str, str], SpatialInterpretationProfile] = {}
        for provider in self._providers:
            for profile in provider.list_profiles():
                identity = (profile.id, profile.version)
                if identity in by_identity:
                    raise RegionDataError(
                        "duplicate spatial interpretation profile: "
                        f"{profile.id}@{profile.version}"
                    )
                by_identity[identity] = profile
        return tuple(by_identity[key] for key in sorted(by_identity))

    def resolve(
        self,
        profile: str = "default",
        profile_version: str = "current",
    ) -> ResolvedSpatialProfile:
        """Resolve exactly one provider's profile selection."""

        # Additional directories extend discovery but never replace the primary
        # provider's application-wide default.
        providers = self._providers[:1] if profile == "default" else self._providers
        matches: list[ResolvedSpatialProfile] = []
        for provider in providers:
            try:
                matches.append(provider.resolve(profile, profile_version))
            except SpatialProfileNotFoundError:
                continue
        if not matches:
            available = ", ".join(sorted({item.id for item in self.list_profiles()}))
            raise SpatialProfileNotFoundError(
                "unknown spatial interpretation profile or version "
                f"{profile!r}@{profile_version!r}; available profiles: {available}"
            )
        if len(matches) > 1:
            raise RegionDataError(
                "spatial interpretation profile selection is ambiguous: "
                f"{profile!r}@{profile_version!r}"
            )
        return matches[0]


class DirectorySpatialProfileProvider:
    """Auto-discover self-describing profile manifests below one directory."""

    def __init__(
        self,
        root: Resource,
        *,
        default_identity: tuple[str, str] | None = None,
    ) -> None:
        self._root = root
        self._default_identity = default_identity
        self._datasets = self._discover(root)
        if not self._datasets:
            raise RegionDataError("profile directory contains no manifest.json files")
        if default_identity is not None and default_identity not in self._datasets:
            profile_id, version = default_identity
            raise RegionDataError(
                "profile-settings.json selects an unavailable default spatial "
                f"profile: {profile_id}@{version}; update the default selection "
                "when renaming its manifest identity"
            )

    @classmethod
    def bundled(cls) -> DirectorySpatialProfileProvider:
        """Return the auto-discovered profiles shipped with :mod:`cfregions`."""

        data_root = files("cfregions").joinpath("data")
        return cls(
            data_root.joinpath("profiles"),
            default_identity=cls._read_default_identity(data_root),
        )

    @classmethod
    def from_data_directory(
        cls, data_directory: str | Path
    ) -> DirectorySpatialProfileProvider:
        """Load profiles and the default selection from a complete data root."""

        path = cls._directory(data_directory, label="data directory")
        return cls(
            path.joinpath("profiles"),
            default_identity=cls._read_default_identity(path),
        )

    @classmethod
    def from_profile_directory(
        cls, profile_directory: str | Path
    ) -> DirectorySpatialProfileProvider:
        """Auto-discover additional profiles without defining a global default."""

        return cls(cls._directory(profile_directory, label="profile directory"))

    def list_profiles(self) -> tuple[SpatialInterpretationProfile, ...]:
        """Return all discovered profile versions in stable identity order."""

        return tuple(self._datasets[identity].info for identity in sorted(self._datasets))

    def resolve(
        self,
        profile: str = "default",
        profile_version: str = "current",
    ) -> ResolvedSpatialProfile:
        """Resolve a discovered profile identity and its convenient aliases."""

        requested_profile = str(profile).strip()
        requested_version = str(profile_version).strip()
        if requested_profile == "default":
            if self._default_identity is None:
                raise SpatialProfileNotFoundError(
                    "this profile directory does not define the global default"
                )
            profile_id = self._default_identity[0]
        else:
            profile_id = requested_profile

        versions = tuple(
            version for candidate_id, version in self._datasets if candidate_id == profile_id
        )
        if not versions:
            raise SpatialProfileNotFoundError(
                f"unknown spatial interpretation profile {requested_profile!r}"
            )
        if requested_version == "current":
            if self._default_identity is not None and profile_id == self._default_identity[0]:
                version = self._default_identity[1]
            elif len(versions) == 1:
                version = versions[0]
            else:
                available = ", ".join(sorted(versions))
                raise SpatialProfileNotFoundError(
                    f"profile {profile_id!r} has multiple versions; specify one of: "
                    f"{available}"
                )
        else:
            version = requested_version

        try:
            dataset = self._datasets[(profile_id, version)]
        except KeyError as error:
            available = ", ".join(sorted(versions))
            raise SpatialProfileNotFoundError(
                f"unknown version {requested_version!r} for spatial interpretation "
                f"profile {profile_id!r}; available versions: {available}"
            ) from error
        return ResolvedSpatialProfile(info=dataset.info, dataset=dataset)

    def _discover(
        self, root: Resource
    ) -> dict[tuple[str, str], SpatialProfileDataset]:
        datasets: dict[tuple[str, str], SpatialProfileDataset] = {}

        def visit(directory: Resource, depth: int) -> None:
            if depth > 4:
                return
            try:
                children = sorted(directory.iterdir(), key=lambda item: item.name)
            except OSError as error:
                raise RegionDataError("unable to scan profile directory") from error
            for child in children:
                if child.name.startswith("."):
                    continue
                if child.is_dir():
                    visit(child, depth + 1)
                elif child.name == "manifest.json":
                    dataset = SpatialProfileDataset(
                        directory,
                        manifest_file="manifest.json",
                    )
                    identity = (dataset.info.id, dataset.info.version)
                    if identity in datasets:
                        raise RegionDataError(
                            "duplicate spatial interpretation profile in one directory: "
                            f"{dataset.info.id}@{dataset.info.version}"
                        )
                    if identity == self._default_identity:
                        dataset = SpatialProfileDataset(
                            directory,
                            manifest_file="manifest.json",
                            is_default=True,
                        )
                    datasets[identity] = dataset

        visit(root, 0)
        return datasets

    @staticmethod
    def _directory(value: str | Path, *, label: str) -> Path:
        path = Path(value).expanduser().resolve()
        if not path.is_dir():
            raise RegionDataError(f"{label} does not exist: {path}")
        return path

    @staticmethod
    def _read_default_identity(root: Resource) -> tuple[str, str]:
        try:
            value = json.loads(root.joinpath("profile-settings.json").read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RegionDataError("unable to read profile-settings.json") from error
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise RegionDataError("profile-settings.json is invalid")
        default = value.get("default_profile")
        if not isinstance(default, dict):
            raise RegionDataError("profile-settings.json default_profile must be an object")
        profile_id = default.get("id")
        version = default.get("version")
        if not isinstance(profile_id, str) or not profile_id:
            raise RegionDataError("default profile id must be a non-empty string")
        if not isinstance(version, str) or not version:
            raise RegionDataError("default profile version must be a non-empty string")
        return profile_id, version
