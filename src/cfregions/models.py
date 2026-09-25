"""Stable, presentation-independent domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

RegionKind = Literal["area", "section"]
MatchRelation = Literal["covered_by", "near_section", "ancestor"]
HierarchyEdgeOrigin = str
GeometryResolution = str
GeometryValidationMode = Literal["runtime", "prevalidated"]


@dataclass(frozen=True, slots=True)
class SpatialInterpretationProfile:
    """Identity and purpose of one selectable spatial interpretation."""

    id: str
    version: str
    title: str
    description: str
    basis: str
    scope: str
    license: str
    homepage: str
    is_default: bool
    cf_versions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-ready profile metadata."""

        return asdict(self)


@dataclass(frozen=True, slots=True)
class GeometryProcessing:
    """Profile-defined deterministic processing for one representation."""

    method: str
    parameters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class GeometryRepresentation:
    """One selectable rendering representation in a mapping release."""

    resolution: GeometryResolution
    label: str
    description: str
    sha256: str | None
    validation_mode: GeometryValidationMode
    processing: GeometryProcessing


@dataclass(frozen=True, slots=True)
class MappingReference:
    """Stable identity of the spatial interpretation used for a lookup."""

    id: str
    version: str
    geometry_resolution: GeometryResolution
    behavior_version: str
    crs: str
    created_at: str
    geometry_sha256: str | None
    geometry_validation: GeometryValidationMode


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Source and derivation used to produce one match."""

    name: str
    version: str
    uri: str
    license: str
    method: str


@dataclass(frozen=True, slots=True)
class Region:
    """Metadata for one name in a CF Standardized Region List release."""

    name: str
    kind: RegionKind
    geometry_type: str
    parents: tuple[str, ...]
    description: str
    hierarchy_path: tuple[str, ...]
    nvs_concept_url: str
    geometry_source: str
    geometry_source_url: str
    geometry_source_version: str
    geometry_license: str
    geometry_method: str
    geometry_contexts: tuple[str, ...]
    specificity: int

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-ready metadata."""

        return asdict(self)


@dataclass(frozen=True, slots=True)
class HierarchyEdge:
    """One directed child-to-parent link with explicit derivation provenance."""

    child: str
    parent: str
    origin: HierarchyEdgeOrigin
    source: SourceReference
    source_path: tuple[str, ...]
    cf_version: str
    mapping: MappingReference

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready hierarchy edge."""

        return asdict(self)


@dataclass(frozen=True, slots=True)
class RegionMatch:
    """A reproducible direct or hierarchy-expanded result for a queried point."""

    region: Region
    relation: MatchRelation
    cf_version: str
    mapping: MappingReference
    method: str
    predicate: str
    source: SourceReference
    distance_km: float | None = None

    @property
    def name(self) -> str:
        """Return the matched standardized name."""

        return self.region.name

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready result including lookup and source provenance."""

        result: dict[str, Any] = {
            "name": self.name,
            "kind": self.region.kind,
            "relation": self.relation,
            "predicate": self.predicate,
            "method": self.method,
            "cf_version": self.cf_version,
            "mapping": asdict(self.mapping),
            "source": asdict(self.source),
        }
        if self.distance_km is not None:
            result["distance_km"] = round(self.distance_km, 6)
        return result


@dataclass(frozen=True, slots=True)
class DatasetInfo:
    """Version and provenance of a selected spatial interpretation profile."""

    schema_version: int
    dataset_id: str
    profile: SpatialInterpretationProfile
    mapping_id: str
    mapping_version: str
    lookup_geometry_sha256: str | None
    generated_on: str
    crs: str
    lookup_behavior_version: str
    lookup_geometry_resolution: GeometryResolution
    lookup_geometry_validation: GeometryValidationMode
    default_geometry_resolution: GeometryResolution
    area_predicate: str
    boundary_inclusive: bool
    section_method: str
    geometry_representations: tuple[GeometryRepresentation, ...]
    region_count: int
    cf_version: str
    cf_is_default: bool
    cf_date: str
    cf_url: str
    vocabulary_sha256: str
    hierarchy_name: str
    hierarchy_version: str
    hierarchy_date: str
    hierarchy_url: str
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-ready metadata."""

        return asdict(self)
