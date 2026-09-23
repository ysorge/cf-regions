"""Independent CF vocabulary and spatial-profile dataset loading."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from .errors import (
    CFVersionNotFoundError,
    RegionDataError,
    SpatialProfileCompatibilityError,
)
from .models import (
    DatasetInfo,
    GeometryProcessing,
    GeometryRepresentation,
    SourceReference,
    SpatialInterpretationProfile,
)


class Resource(Protocol):
    """Filesystem-like operations needed from package resources and paths."""

    @property
    def name(self) -> str: ...

    def joinpath(self, child: str) -> Resource: ...

    def read_bytes(self) -> bytes: ...

    def iterdir(self) -> Any: ...

    def is_dir(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class CFRelease:
    """Validated profile-independent metadata for one CF vocabulary release."""

    schema_version: int
    dataset_id: str
    version: str
    is_default: bool
    date: str
    url: str
    vocabulary_sha256: str
    descriptions: dict[str, str]


@dataclass(frozen=True, slots=True)
class ProfileHierarchyEdge:
    """One profile-defined hierarchy edge before runtime provenance is attached."""

    child: str
    parent: str
    origin: str
    source: SourceReference
    source_path: tuple[str, ...]
    context_path: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GeometryResource:
    """A declared GeoJSON representation that can be loaded on demand."""

    resolution: str
    label: str
    description: str
    geometry_file: str
    sha256: str
    feature_count: int
    processing: GeometryProcessing


@dataclass(frozen=True, slots=True)
class DatasetBundle:
    """A selected CF release combined with one compatible spatial profile."""

    feature_collection: dict[str, Any]
    info: DatasetInfo
    geometry_resources: tuple[GeometryResource, ...]
    hierarchy_edges: tuple[ProfileHierarchyEdge, ...]


class _ResourceLoader:
    """Safe reads relative to one immutable resource root."""

    def __init__(self, root: Resource) -> None:
        self._root = root

    def _resource(self, relative_path: str) -> Resource:
        path = PurePosixPath(relative_path)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise RegionDataError(f"invalid data resource path: {relative_path!r}")
        resource = self._root
        for part in path.parts:
            resource = resource.joinpath(part)
        return resource

    def _read_bytes(self, relative_path: str) -> bytes:
        try:
            return self._resource(relative_path).read_bytes()
        except OSError as error:
            raise RegionDataError(f"unable to read data resource: {relative_path}") from error

    def _read_json(self, relative_path: str) -> dict[str, Any]:
        try:
            value = json.loads(self._read_bytes(relative_path))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RegionDataError(f"data resource is not valid JSON: {relative_path}") from error
        if not isinstance(value, dict):
            raise RegionDataError(f"data resource must be a JSON object: {relative_path}")
        return value

    @staticmethod
    def _verify_sha256(content: bytes, *, expected: str, label: str) -> None:
        actual = hashlib.sha256(content).hexdigest()
        if actual != expected:
            raise RegionDataError(
                f"checksum mismatch for {label}: expected {expected}, found {actual}"
            )

    @staticmethod
    def _required_mapping(value: dict[str, Any], key: str) -> dict[str, Any]:
        result = value.get(key)
        if not isinstance(result, dict):
            raise RegionDataError(f"data manifest field {key!r} must be an object")
        return result

    @staticmethod
    def _required_string(value: dict[str, Any], key: str) -> str:
        result = value.get(key)
        if not isinstance(result, str) or not result:
            raise RegionDataError(f"data manifest field {key!r} must be a string")
        return result

    @staticmethod
    def _required_int(value: dict[str, Any], key: str) -> int:
        result = value.get(key)
        if isinstance(result, bool) or not isinstance(result, int):
            raise RegionDataError(f"data manifest field {key!r} must be an integer")
        return result

    @staticmethod
    def _required_bool(value: dict[str, Any], key: str) -> bool:
        result = value.get(key)
        if not isinstance(result, bool):
            raise RegionDataError(f"data manifest field {key!r} must be a boolean")
        return result

    @classmethod
    def _validate_schema_version(cls, value: dict[str, Any], *, label: str) -> None:
        version = cls._required_int(value, "schema_version")
        if version != 1:
            raise RegionDataError(
                f"unsupported {label} schema version {version}; supported version: 1"
            )


class CFRegistry(_ResourceLoader):
    """Discover and validate profile-independent CF vocabulary releases."""

    def __init__(self, root: Resource, *, catalog_file: str = "catalog.json") -> None:
        super().__init__(root)
        self._catalog = self._read_json(catalog_file)
        self._validate_schema_version(self._catalog, label=catalog_file)
        try:
            self._default_version = str(self._catalog["default_version"])
            raw_versions = self._catalog["versions"]
            raw_aliases = self._catalog.get("aliases", {})
            if not isinstance(raw_versions, dict) or not isinstance(raw_aliases, dict):
                raise TypeError
            self._versions = {str(key): str(value) for key, value in raw_versions.items()}
            self._aliases = {str(key): str(value) for key, value in raw_aliases.items()}
        except (KeyError, TypeError, ValueError) as error:
            raise RegionDataError("CF catalog.json is invalid") from error
        if self._default_version not in self._versions:
            raise RegionDataError("CF default_version is not declared in versions")

    @classmethod
    def bundled(cls) -> CFRegistry:
        """Return the CF registry shipped with :mod:`cfregions`."""

        return cls(files("cfregions").joinpath("data"))

    @classmethod
    def from_directory(cls, data_directory: str | Path) -> CFRegistry:
        """Load a CF registry from a compatible data-root directory."""

        path = Path(data_directory).expanduser().resolve()
        if not path.is_dir():
            raise RegionDataError(f"data directory does not exist: {path}")
        return cls(path)

    @property
    def default_version(self) -> str:
        """Return the numbered release selected by the ``current`` alias."""

        return self._default_version

    def list_versions(self) -> tuple[str, ...]:
        """Return available numbered CF releases in numeric-aware order."""

        numeric = sorted((value for value in self._versions if value.isdigit()), key=int)
        named = sorted(value for value in self._versions if not value.isdigit())
        return tuple((*numeric, *named))

    def resolve_version(self, cf_version: str = "current") -> str:
        """Resolve a numbered release or alias to a declared CF version."""

        requested = str(cf_version).strip()
        resolved = self._aliases.get(requested, requested)
        if resolved not in self._versions:
            available = ", ".join(self.list_versions())
            raise CFVersionNotFoundError(
                f"unknown CF region version {requested!r}; available versions: {available}"
            )
        return resolved

    def load(self, cf_version: str = "current") -> CFRelease:
        """Load one CF release without selecting any spatial interpretation."""

        resolved = self.resolve_version(cf_version)
        manifest_file = self._versions[resolved]
        manifest = self._read_json(manifest_file)
        self._validate_schema_version(manifest, label=manifest_file)
        cf = self._required_mapping(manifest, "cf")
        declared = self._required_string(cf, "version")
        if declared != resolved:
            raise RegionDataError(
                f"version manifest declares CF {declared}, expected {resolved}"
            )
        vocabulary_file = self._required_string(cf, "vocabulary_file")
        vocabulary_bytes = self._read_bytes(vocabulary_file)
        vocabulary_sha256 = self._required_string(cf, "sha256")
        self._verify_sha256(
            vocabulary_bytes, expected=vocabulary_sha256, label=vocabulary_file
        )
        version, vocabulary_date, descriptions = self._parse_vocabulary(vocabulary_bytes)
        if version != resolved:
            raise RegionDataError(
                f"{vocabulary_file} declares version {version}, expected {resolved}"
            )
        if vocabulary_date != self._required_string(cf, "date"):
            raise RegionDataError(f"{vocabulary_file} date does not match its manifest")
        declared_count = self._required_int(manifest, "region_count")
        if declared_count != len(descriptions):
            raise RegionDataError(
                f"version {resolved} declares {declared_count} regions; "
                f"vocabulary has {len(descriptions)}"
            )
        return CFRelease(
            schema_version=self._required_int(manifest, "schema_version"),
            dataset_id=self._required_string(manifest, "dataset_id"),
            version=resolved,
            is_default=resolved == self._default_version,
            date=vocabulary_date,
            url=self._required_string(cf, "url"),
            vocabulary_sha256=vocabulary_sha256,
            descriptions=descriptions,
        )

    @staticmethod
    def _parse_vocabulary(content: bytes) -> tuple[str, str, dict[str, str]]:
        try:
            root = ET.fromstring(content)
            version = (root.findtext("version_number") or "").strip()
            date = (root.findtext("date") or "").strip()
            descriptions = {
                str(entry.attrib["id"]): (entry.findtext("description") or "").strip()
                for entry in root.findall("entry")
            }
        except (ET.ParseError, KeyError, TypeError) as error:
            raise RegionDataError("CF vocabulary XML is invalid") from error
        if not version or not date or not descriptions:
            raise RegionDataError("CF vocabulary XML lacks version, date, or entries")
        return version, date, descriptions


class SpatialProfileDataset(_ResourceLoader):
    """Load one self-describing profile version independently of CF metadata."""

    def __init__(
        self,
        root: Resource,
        *,
        manifest_file: str,
        is_default: bool = False,
    ) -> None:
        super().__init__(root)
        self._manifest = self._read_json(manifest_file)
        self._validate_schema_version(self._manifest, label=manifest_file)
        raw_profile = self._required_mapping(self._manifest, "profile")
        raw_versions = self._manifest.get("supported_cf_versions")
        if (
            not isinstance(raw_versions, list)
            or not raw_versions
            or any(not isinstance(value, str) or not value for value in raw_versions)
        ):
            raise RegionDataError("profile supported_cf_versions must be a non-empty array")
        supported_versions = tuple(str(value) for value in raw_versions)
        if len(set(supported_versions)) != len(supported_versions):
            raise RegionDataError("profile supported_cf_versions contains duplicates")
        self._info = SpatialInterpretationProfile(
            id=self._required_string(raw_profile, "id"),
            version=self._required_string(raw_profile, "version"),
            title=self._required_string(raw_profile, "title"),
            description=self._required_string(raw_profile, "description"),
            basis=self._required_string(raw_profile, "basis"),
            scope=self._required_string(raw_profile, "scope"),
            license=self._required_string(raw_profile, "license"),
            homepage=self._required_string(raw_profile, "homepage"),
            is_default=is_default,
            cf_versions=supported_versions,
        )
        self._geometry_resources_cache = self._geometry_resources(self._manifest)

    @property
    def info(self) -> SpatialInterpretationProfile:
        """Return the profile identity declared by its own manifest."""

        return self._info

    def load(self, cf_release: CFRelease) -> DatasetBundle:
        """Combine this profile with one compatible, independently loaded CF release."""

        if cf_release.version not in self._info.cf_versions:
            available = ", ".join(self._info.cf_versions)
            raise SpatialProfileCompatibilityError(
                f"spatial profile {self._info.id}@{self._info.version} does not support "
                f"CF version {cf_release.version}; supported versions: {available}"
            )
        lookup = self._required_mapping(self._manifest, "lookup")
        if self._required_string(lookup, "area_predicate") != "covers" or not (
            self._required_bool(lookup, "boundary_inclusive")
        ):
            raise RegionDataError(
                "profile lookup behavior is unsupported; cf-regions requires "
                "boundary-inclusive covers semantics"
            )
        if self._required_string(lookup, "section_method") != "minor_great_circle_distance":
            raise RegionDataError(
                "profile section_method is unsupported; expected minor_great_circle_distance"
            )
        resources = {item.resolution: item for item in self._geometry_resources_cache}
        lookup_resolution = self._required_string(lookup, "geometry_resolution")
        try:
            lookup_resource = resources[lookup_resolution]
        except KeyError as error:
            raise RegionDataError(
                "profile lookup geometry_resolution is not a declared representation"
            ) from error
        default_resolution = self._required_string(lookup, "default_geometry_resolution")
        if default_resolution not in resources:
            raise RegionDataError(
                "profile default_geometry_resolution is not a declared representation"
            )
        collection = self._select_features(
            self.load_geometry(lookup_resource),
            descriptions=cf_release.descriptions,
            cf_version=cf_release.version,
        )
        hierarchy = self._required_mapping(self._manifest, "hierarchy")
        hierarchy_edges = self._load_hierarchy(
            hierarchy, region_names=frozenset(cf_release.descriptions)
        )
        raw_limitations = self._manifest.get("limitations")
        if not isinstance(raw_limitations, list) or any(
            not isinstance(value, str) for value in raw_limitations
        ):
            raise RegionDataError("profile limitations must be an array of strings")
        info = DatasetInfo(
            schema_version=self._required_int(self._manifest, "schema_version"),
            dataset_id=f"{cf_release.dataset_id}__{self._info.id}-{self._info.version}",
            profile=self._info,
            mapping_id=self._info.id,
            mapping_version=self._info.version,
            lookup_geometry_sha256=lookup_resource.sha256,
            generated_on=self._required_string(self._manifest, "generated_on"),
            crs=self._required_string(self._manifest, "crs"),
            lookup_behavior_version=self._required_string(lookup, "behavior_version"),
            lookup_geometry_resolution=lookup_resolution,
            default_geometry_resolution=default_resolution,
            area_predicate=self._required_string(lookup, "area_predicate"),
            boundary_inclusive=self._required_bool(lookup, "boundary_inclusive"),
            section_method=self._required_string(lookup, "section_method"),
            geometry_representations=tuple(
                GeometryRepresentation(
                    resolution=item.resolution,
                    label=item.label,
                    description=item.description,
                    sha256=item.sha256,
                    processing=item.processing,
                )
                for item in self._geometry_resources_cache
            ),
            region_count=len(cf_release.descriptions),
            cf_version=cf_release.version,
            cf_is_default=cf_release.is_default,
            cf_date=cf_release.date,
            cf_url=cf_release.url,
            vocabulary_sha256=cf_release.vocabulary_sha256,
            hierarchy_name=self._required_string(hierarchy, "name"),
            hierarchy_version=self._required_string(hierarchy, "version"),
            hierarchy_date=self._required_string(hierarchy, "date"),
            hierarchy_url=self._required_string(hierarchy, "url"),
            limitations=tuple(raw_limitations),
        )
        return DatasetBundle(
            feature_collection=collection,
            info=info,
            geometry_resources=self._geometry_resources_cache,
            hierarchy_edges=hierarchy_edges,
        )

    def load_geometry(self, resource: GeometryResource) -> dict[str, Any]:
        """Load and checksum one declared profile geometry representation."""

        content = self._read_bytes(resource.geometry_file)
        self._verify_sha256(content, expected=resource.sha256, label=resource.geometry_file)
        try:
            collection = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RegionDataError(
                f"{resource.geometry_file} is not valid UTF-8 JSON"
            ) from error
        if not isinstance(collection, dict):
            raise RegionDataError(f"{resource.geometry_file} must contain a JSON object")
        features = collection.get("features")
        if not isinstance(features, list) or len(features) != resource.feature_count:
            actual = len(features) if isinstance(features, list) else 0
            raise RegionDataError(
                f"geometry representation {resource.resolution!r} declares "
                f"{resource.feature_count} features; loaded {actual}"
            )
        return collection

    def _load_hierarchy(
        self,
        metadata: dict[str, Any],
        *,
        region_names: frozenset[str],
    ) -> tuple[ProfileHierarchyEdge, ...]:
        hierarchy_file = self._required_string(metadata, "hierarchy_file")
        content = self._read_bytes(hierarchy_file)
        self._verify_sha256(
            content,
            expected=self._required_string(metadata, "sha256"),
            label=hierarchy_file,
        )
        try:
            value = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RegionDataError(f"{hierarchy_file} is not valid UTF-8 JSON") from error
        if not isinstance(value, dict):
            raise RegionDataError(f"{hierarchy_file} must contain a JSON object")
        self._validate_schema_version(value, label=hierarchy_file)
        raw_edges = value.get("edges")
        if not isinstance(raw_edges, list):
            raise RegionDataError("profile hierarchy edges must be an array")
        if len(raw_edges) != self._required_int(metadata, "edge_count"):
            raise RegionDataError("profile hierarchy edge count does not match its manifest")
        edges: list[ProfileHierarchyEdge] = []
        identities: set[tuple[str, str]] = set()
        for raw_edge in raw_edges:
            if not isinstance(raw_edge, dict):
                raise RegionDataError("profile hierarchy contains an invalid edge")
            child = self._required_string(raw_edge, "child")
            parent = self._required_string(raw_edge, "parent")
            if self._required_string(raw_edge, "relation") != "broader":
                raise RegionDataError("profile hierarchy supports only broader relations")
            if child not in region_names or parent not in region_names:
                continue
            identity = (child, parent)
            if identity in identities:
                raise RegionDataError(f"profile hierarchy duplicates edge {child} -> {parent}")
            identities.add(identity)
            raw_source = self._required_mapping(raw_edge, "source")
            raw_path = raw_edge.get("source_path", [])
            raw_context_path = raw_edge.get("context_path", [])
            if not isinstance(raw_path, list) or not isinstance(raw_context_path, list):
                raise RegionDataError(
                    "profile hierarchy source_path and context_path must be arrays"
                )
            edges.append(
                ProfileHierarchyEdge(
                    child=child,
                    parent=parent,
                    origin=self._required_string(raw_edge, "origin"),
                    source=SourceReference(
                        name=self._required_string(raw_source, "name"),
                        version=self._required_string(raw_source, "version"),
                        uri=self._required_string(raw_source, "uri"),
                        license=self._required_string(raw_source, "license"),
                        method=self._required_string(raw_source, "method"),
                    ),
                    source_path=tuple(str(item) for item in raw_path),
                    context_path=tuple(str(item) for item in raw_context_path),
                )
            )
        return tuple(edges)

    @classmethod
    def _geometry_resources(
        cls, manifest: dict[str, Any]
    ) -> tuple[GeometryResource, ...]:
        representations = manifest.get("representations")
        if not isinstance(representations, dict) or not representations:
            raise RegionDataError("profile representations must be a non-empty object")
        resources: list[GeometryResource] = []
        for resolution, raw_resource in representations.items():
            if not isinstance(resolution, str) or not resolution or not isinstance(
                raw_resource, dict
            ):
                raise RegionDataError("geometry representation metadata is invalid")
            processing = cls._required_mapping(raw_resource, "processing")
            parameters = cls._required_mapping(processing, "parameters")
            resources.append(
                GeometryResource(
                    resolution=resolution,
                    label=cls._required_string(raw_resource, "label"),
                    description=cls._required_string(raw_resource, "description"),
                    geometry_file=cls._required_string(raw_resource, "geometry_file"),
                    sha256=cls._required_string(raw_resource, "sha256"),
                    feature_count=cls._required_int(raw_resource, "feature_count"),
                    processing=GeometryProcessing(
                        method=cls._required_string(processing, "method"),
                        parameters=parameters,
                    ),
                )
            )
        return tuple(resources)

    @staticmethod
    def _select_features(
        collection: dict[str, Any],
        *,
        descriptions: dict[str, str],
        cf_version: str,
    ) -> dict[str, Any]:
        features = collection.get("features")
        if collection.get("type") != "FeatureCollection" or not isinstance(features, list):
            raise RegionDataError("geometry is not a GeoJSON FeatureCollection")
        names = frozenset(descriptions)
        selected: list[dict[str, Any]] = []
        selected_names: set[str] = set()
        for feature in features:
            if not isinstance(feature, dict):
                continue
            properties = feature.get("properties")
            if not isinstance(properties, dict) or properties.get("name") not in names:
                continue
            name = str(properties["name"])
            selected.append(
                {**feature, "properties": {**properties, "description": descriptions[name]}}
            )
            selected_names.add(name)
        missing = names - selected_names
        if missing:
            raise RegionDataError(
                f"profile geometry lacks CF v{cf_version} region(s): "
                + ", ".join(sorted(missing))
            )
        return {**collection, "features": selected}
