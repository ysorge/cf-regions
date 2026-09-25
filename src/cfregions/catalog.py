"""Geometry repository and point-matching service."""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Iterator, Sequence
from itertools import pairwise
from pathlib import Path
from typing import Any

from shapely.geometry import LineString, MultiLineString, Point, box
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

from .datasets import (
    CFRegistry,
    DatasetBundle,
    GeometryResource,
    GeometryStore,
    ProfileHierarchyEdge,
    SpatialProfileDataset,
)
from .errors import (
    CoordinateError,
    GeometryResolutionNotFoundError,
    RegionDataError,
    RegionNotFoundError,
)
from .models import (
    DatasetInfo,
    HierarchyEdge,
    MappingReference,
    Region,
    RegionMatch,
    SourceReference,
)

_EARTH_MEAN_RADIUS_KM = 6371.0088

CoordinatePair = str | Sequence[float]


def _number(value: object, *, argument_name: str) -> float:
    if isinstance(value, (bool, str, bytes)):
        raise CoordinateError(f"{argument_name} must be a finite number")
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError) as error:
        raise CoordinateError(f"{argument_name} must be a finite number") from error
    if not math.isfinite(result):
        raise CoordinateError(f"{argument_name} must be a finite number")
    return result


def validate_coordinates(*, longitude: object, latitude: object) -> tuple[float, float]:
    """Validate WGS84 coordinates and return floats in longitude/latitude order."""

    checked_longitude = _number(longitude, argument_name="longitude")
    checked_latitude = _number(latitude, argument_name="latitude")
    if not -180.0 <= checked_longitude <= 180.0:
        raise CoordinateError("longitude must be between -180 and 180 degrees")
    if not -90.0 <= checked_latitude <= 90.0:
        raise CoordinateError("latitude must be between -90 and 90 degrees")
    return checked_longitude, checked_latitude


def _parse_coordinate_pair(
    value: CoordinatePair, *, argument_name: str
) -> tuple[float, float]:
    if isinstance(value, str):
        components: Sequence[object] = value.split(",")
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        components = value
    else:
        raise CoordinateError(
            f"{argument_name} must contain two comma-separated finite numbers"
        )
    if len(components) != 2:
        raise CoordinateError(
            f"{argument_name} must contain exactly two comma-separated numbers"
        )

    numbers: list[float] = []
    for component in components:
        if isinstance(component, bool) or not isinstance(component, (str, int, float)):
            raise CoordinateError(f"{argument_name} must contain two finite numbers")
        try:
            number = float(component)
        except (TypeError, ValueError, OverflowError) as error:
            raise CoordinateError(
                f"{argument_name} must contain two finite numbers"
            ) from error
        if not math.isfinite(number):
            raise CoordinateError(f"{argument_name} must contain two finite numbers")
        numbers.append(number)
    return numbers[0], numbers[1]


def resolve_coordinates(
    *,
    longitude: object | None = None,
    latitude: object | None = None,
    lonlat: CoordinatePair | None = None,
    latlon: CoordinatePair | None = None,
) -> tuple[float, float]:
    """Resolve exactly one coordinate form and return longitude, latitude."""

    separate_coordinates = longitude is not None or latitude is not None
    supplied_forms = sum(
        (separate_coordinates, lonlat is not None, latlon is not None)
    )
    if supplied_forms == 0:
        raise CoordinateError(
            "provide coordinates as longitude/latitude, lonlat, or latlon"
        )
    if supplied_forms > 1:
        raise CoordinateError(
            "coordinate arguments are ambiguous; use exactly one of "
            "longitude/latitude, lonlat, or latlon"
        )
    if separate_coordinates:
        if longitude is None or latitude is None:
            raise CoordinateError("longitude and latitude must be provided together")
        return validate_coordinates(longitude=longitude, latitude=latitude)
    if lonlat is not None:
        parsed_longitude, parsed_latitude = _parse_coordinate_pair(
            lonlat, argument_name="lonlat"
        )
    else:
        assert latlon is not None
        parsed_latitude, parsed_longitude = _parse_coordinate_pair(
            latlon, argument_name="latlon"
        )
    return validate_coordinates(
        longitude=parsed_longitude,
        latitude=parsed_latitude,
    )


def validate_section_tolerance(value: object) -> float:
    """Validate a non-negative section proximity tolerance in kilometers."""

    tolerance = _number(value, argument_name="section_tolerance_km")
    if tolerance < 0.0:
        raise CoordinateError("section_tolerance_km must be greater than or equal to 0")
    return tolerance


def _unit_vector(longitude: float, latitude: float) -> tuple[float, float, float]:
    longitude_radians = math.radians(longitude)
    latitude_radians = math.radians(latitude)
    latitude_cosine = math.cos(latitude_radians)
    return (
        latitude_cosine * math.cos(longitude_radians),
        latitude_cosine * math.sin(longitude_radians),
        math.sin(latitude_radians),
    )


def _dot(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return sum(
        left_value * right_value
        for left_value, right_value in zip(left, right, strict=True)
    )


def _cross(
    left: tuple[float, float, float], right: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _norm(vector: tuple[float, float, float]) -> float:
    return math.sqrt(_dot(vector, vector))


def _normalize(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    length = _norm(vector)
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _angular_distance(
    left: tuple[float, float, float], right: tuple[float, float, float]
) -> float:
    return math.acos(max(-1.0, min(1.0, _dot(left, right))))


def _segment_distance_km(
    *,
    longitude: float,
    latitude: float,
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    """Return spherical distance to the minor great-circle arc in kilometers."""

    point_vector = _unit_vector(longitude, latitude)
    start_vector = _unit_vector(*start)
    end_vector = _unit_vector(*end)
    arc_length = _angular_distance(start_vector, end_vector)
    endpoint_distance = min(
        _angular_distance(point_vector, start_vector),
        _angular_distance(point_vector, end_vector),
    )
    normal = _cross(start_vector, end_vector)
    if arc_length < 1e-12 or _norm(normal) < 1e-12:
        return endpoint_distance * _EARTH_MEAN_RADIUS_KM

    unit_normal = _normalize(normal)
    projection = (
        point_vector[0] - _dot(point_vector, unit_normal) * unit_normal[0],
        point_vector[1] - _dot(point_vector, unit_normal) * unit_normal[1],
        point_vector[2] - _dot(point_vector, unit_normal) * unit_normal[2],
    )
    if _norm(projection) < 1e-12:
        return endpoint_distance * _EARTH_MEAN_RADIUS_KM

    nearest = _normalize(projection)
    opposite = (-nearest[0], -nearest[1], -nearest[2])
    for candidate in (nearest, opposite):
        candidate_arc = _angular_distance(start_vector, candidate) + _angular_distance(
            candidate, end_vector
        )
        if math.isclose(candidate_arc, arc_length, abs_tol=1e-9):
            angular_distance = _angular_distance(point_vector, candidate)
            return min(angular_distance, endpoint_distance) * _EARTH_MEAN_RADIUS_KM
    return endpoint_distance * _EARTH_MEAN_RADIUS_KM


def _line_parts(geometry: BaseGeometry) -> Iterator[LineString]:
    if isinstance(geometry, LineString):
        yield geometry
    elif isinstance(geometry, MultiLineString):
        yield from geometry.geoms
    elif geometry.geom_type == "GeometryCollection":
        for part in geometry.geoms:
            yield from _line_parts(part)


def _line_distance_km(
    geometry: BaseGeometry,
    *,
    longitude: float,
    latitude: float,
) -> float:
    distances: list[float] = []
    for line in _line_parts(geometry):
        coordinates = list(line.coords)
        distances.extend(
            _segment_distance_km(
                longitude=longitude,
                latitude=latitude,
                start=(float(start[0]), float(start[1])),
                end=(float(end[0]), float(end[1])),
            )
            for start, end in pairwise(coordinates)
        )
    if not distances:
        raise RegionDataError("a section geometry does not contain a line")
    return min(distances)


class RegionCatalog:
    """An immutable, indexed catalog of the bundled CF region interpretation."""

    def __init__(
        self,
        *,
        lookup_store: GeometryStore,
        descriptions: dict[str, str],
        dataset_info: DatasetInfo,
        profile_dataset: SpatialProfileDataset | None = None,
        geometry_resources: tuple[GeometryResource, ...] = (),
        hierarchy_edges: tuple[ProfileHierarchyEdge, ...] = (),
    ) -> None:
        regions: list[Region] = []
        bounds: list[tuple[float, float, float, float]] = []
        names: set[str] = set()
        parents_by_child: dict[str, list[str]] = {}
        paths_by_child: dict[str, tuple[str, ...]] = {}
        edge_definitions: dict[tuple[str, str], ProfileHierarchyEdge] = {}
        for edge in hierarchy_edges:
            identity = (edge.child, edge.parent)
            if identity in edge_definitions:
                raise RegionDataError(
                    f"profile hierarchy duplicates edge {edge.child} -> {edge.parent}"
                )
            edge_definitions[identity] = edge
            parents_by_child.setdefault(edge.child, []).append(edge.parent)
            if edge.context_path:
                paths_by_child.setdefault(edge.child, edge.context_path)

        for record in lookup_store.records:
            if record.name not in descriptions:
                continue
            properties = {
                **record.properties,
                "description": descriptions[record.name],
            }
            name = record.name
            region = self._region_from_properties(
                properties,
                record.geometry_type,
                parents=tuple(parents_by_child.get(name, ())),
                hierarchy_path=paths_by_child.get(name, ()),
            )
            if region.name in names:
                raise RegionDataError(f"duplicate region name: {region.name}")
            names.add(region.name)
            if region.kind == "area" and record.geometry_type not in {
                "Polygon",
                "MultiPolygon",
            }:
                raise RegionDataError(f"area region {region.name} is not polygonal")
            if region.kind == "section" and record.geometry_type not in {
                "LineString",
                "MultiLineString",
            }:
                raise RegionDataError(f"section region {region.name} is not linear")
            regions.append(region)
            bounds.append(record.bounds)

        self._regions = tuple(regions)
        self._name_to_index = {region.name: index for index, region in enumerate(regions)}
        missing = set(descriptions) - set(self._name_to_index)
        if missing:
            raise RegionDataError(
                f"profile geometry lacks CF v{dataset_info.cf_version} region(s): "
                + ", ".join(sorted(missing))
            )
        for region in regions:
            unknown_parents = set(region.parents) - names
            if unknown_parents:
                parent_list = ", ".join(sorted(unknown_parents))
                raise RegionDataError(f"{region.name} has unknown parent(s): {parent_list}")
        self._assert_acyclic()
        self._tree = STRtree(tuple(box(*item) for item in bounds))
        self._section_indexes = tuple(
            index for index, region in enumerate(self._regions) if region.kind == "section"
        )
        if dataset_info.region_count != len(regions):
            raise RegionDataError(
                f"dataset declares {dataset_info.region_count} regions; loaded {len(regions)}"
            )
        self._dataset_info = dataset_info
        unknown_edge_names = {
            value
            for edge in hierarchy_edges
            for value in (edge.child, edge.parent)
            if value not in names
        }
        if unknown_edge_names:
            raise RegionDataError(
                "profile hierarchy refers to unknown region(s): "
                + ", ".join(sorted(unknown_edge_names))
            )
        self._hierarchy_edges = edge_definitions
        self._profile_dataset = profile_dataset
        self._geometry_resources = {
            resource.resolution: resource for resource in geometry_resources
        }
        self._lookup_store = lookup_store
        self._geometry_stores: dict[str, GeometryStore] = {
            dataset_info.lookup_geometry_resolution: lookup_store
        }

    @staticmethod
    def _region_from_properties(
        properties: dict[str, Any],
        geometry_type: str,
        *,
        parents: tuple[str, ...],
        hierarchy_path: tuple[str, ...],
    ) -> Region:
        try:
            kind = str(properties["kind"])
            if kind not in {"area", "section"}:
                raise ValueError("unsupported region kind")
            return Region(
                name=str(properties["name"]),
                kind=kind,  # type: ignore[arg-type]
                geometry_type=geometry_type,
                parents=parents,
                description=str(properties.get("description", "")),
                hierarchy_path=hierarchy_path,
                nvs_concept_url=str(properties["nvs_concept_url"]),
                geometry_source=str(properties["geometry_source"]),
                geometry_source_url=str(properties["geometry_source_url"]),
                geometry_source_version=str(properties["geometry_source_version"]),
                geometry_license=str(properties["geometry_license"]),
                geometry_method=str(properties["geometry_method"]),
                geometry_contexts=tuple(
                    str(value) for value in properties.get("geometry_contexts", [])
                ),
                specificity=int(properties["specificity"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            name = properties.get("name", "<unknown>")
            raise RegionDataError(f"invalid properties for region {name}") from error

    def _assert_acyclic(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visiting:
                raise RegionDataError(f"region hierarchy contains a cycle at {name}")
            if name in visited:
                return
            visiting.add(name)
            for parent in self._regions[self._name_to_index[name]].parents:
                visit(parent)
            visiting.remove(name)
            visited.add(name)

        for region in self._regions:
            visit(region.name)

    @classmethod
    def bundled(cls, *, cf_version: str = "current") -> RegionCatalog:
        """Load a selected release from the package's bundled dataset registry."""

        from .profiles import DirectorySpatialProfileProvider

        profile = DirectorySpatialProfileProvider.bundled().resolve()
        return cls.from_sources(
            CFRegistry.bundled(), profile.dataset, cf_version=cf_version
        )

    @classmethod
    def from_data_directory(
        cls,
        data_directory: str | Path,
        *,
        cf_version: str = "current",
    ) -> RegionCatalog:
        """Load a selected release from a compatible external dataset directory."""

        from .profiles import DirectorySpatialProfileProvider

        profile = DirectorySpatialProfileProvider.from_data_directory(
            data_directory
        ).resolve()
        return cls.from_sources(
            CFRegistry.from_directory(data_directory),
            profile.dataset,
            cf_version=cf_version,
        )

    @classmethod
    def from_sources(
        cls,
        cf_registry: CFRegistry,
        profile_dataset: SpatialProfileDataset,
        *,
        cf_version: str = "current",
    ) -> RegionCatalog:
        """Combine independently selected CF and spatial-profile data."""

        bundle = profile_dataset.load(cf_registry.load(cf_version))
        return cls.from_bundle(profile_dataset, bundle)

    @classmethod
    def from_bundle(
        cls,
        profile_dataset: SpatialProfileDataset,
        bundle: DatasetBundle,
    ) -> RegionCatalog:
        """Build a catalog from an already selected vocabulary/profile bundle."""

        resources = {
            resource.resolution: resource for resource in bundle.geometry_resources
        }
        lookup_resource = resources[bundle.info.lookup_geometry_resolution]
        return cls(
            lookup_store=profile_dataset.open_geometry(lookup_resource),
            descriptions=bundle.descriptions,
            dataset_info=bundle.info,
            profile_dataset=profile_dataset,
            geometry_resources=bundle.geometry_resources,
            hierarchy_edges=bundle.hierarchy_edges,
        )

    @property
    def dataset_info(self) -> DatasetInfo:
        """Return immutable dataset metadata."""

        return self._dataset_info

    def list_regions(self) -> tuple[Region, ...]:
        """Return every region, alphabetically by standardized name."""

        return tuple(sorted(self._regions, key=lambda region: region.name))

    def list_hierarchy_edges(
        self, region_name: str | None = None
    ) -> tuple[HierarchyEdge, ...]:
        """Return all hierarchy edges or the ancestor subgraph of one region."""

        if region_name is None:
            selected_names = set(self._name_to_index)
        else:
            self.get_region(region_name)
            selected_names = {region_name}
            pending = deque((region_name,))
            while pending:
                child_name = pending.popleft()
                child = self._regions[self._name_to_index[child_name]]
                for parent_name in child.parents:
                    if parent_name not in selected_names:
                        selected_names.add(parent_name)
                        pending.append(parent_name)

        edges = [
            self._hierarchy_edge(region, parent_name)
            for region in self._regions
            if region.name in selected_names
            for parent_name in region.parents
        ]
        return tuple(sorted(edges, key=lambda edge: (edge.child, edge.parent)))

    def get_region(self, region_name: str) -> Region:
        """Return metadata for one exact CF standardized name."""

        try:
            return self._regions[self._name_to_index[region_name]]
        except (KeyError, TypeError) as error:
            raise RegionNotFoundError(f"unknown CF standardized region: {region_name}") from error

    def get_region_shape(
        self,
        region_name: str,
        *,
        geometry_resolution: str | None = None,
    ) -> dict[str, Any]:
        """Return one interpreted GeoJSON Feature at a declared resolution."""

        try:
            region = self._regions[self._name_to_index[region_name]]
        except (KeyError, TypeError) as error:
            raise RegionNotFoundError(f"unknown CF standardized region: {region_name}") from error
        resolution = geometry_resolution or self._dataset_info.default_geometry_resolution
        store = self._store_for_resolution(resolution)
        feature = store.feature(region_name)
        artifact = store.resource.lookup_artifact
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise RegionDataError(
                f"geometry representation {resolution!r} has invalid properties for {region_name!r}"
            )
        feature["properties"] = {
            **properties,
            **region.to_dict(),
            "spatial_profile_id": self._dataset_info.profile.id,
            "spatial_profile_version": self._dataset_info.profile.version,
            "mapping_id": self._dataset_info.mapping_id,
            "mapping_version": self._dataset_info.mapping_version,
            "geometry_resolution": resolution,
            "geometry_validation": (
                artifact.validation_mode if artifact is not None else "runtime"
            ),
            "crs": self._dataset_info.crs,
        }
        return feature

    def _store_for_resolution(self, resolution: str) -> GeometryStore:
        cached = self._geometry_stores.get(resolution)
        if cached is not None:
            return cached
        resource = self._geometry_resources.get(resolution)
        available = ", ".join(sorted(self._geometry_resources))
        if resource is None or self._profile_dataset is None:
            raise GeometryResolutionNotFoundError(
                f"unknown geometry resolution {resolution!r}; available: {available}"
            )
        store = self._profile_dataset.open_geometry(resource)
        missing = set(self._name_to_index) - {
            record.name for record in store.records
        }
        if missing:
            raise RegionDataError(
                f"geometry representation {resolution!r} lacks CF region(s): "
                + ", ".join(sorted(missing))
            )
        self._geometry_stores[resolution] = store
        return store

    def _mapping_reference(self) -> MappingReference:
        info = self._dataset_info
        return MappingReference(
            id=info.mapping_id,
            version=info.mapping_version,
            geometry_resolution=info.lookup_geometry_resolution,
            behavior_version=info.lookup_behavior_version,
            crs=info.crs,
            created_at=info.generated_on,
            geometry_sha256=info.lookup_geometry_sha256,
            geometry_validation=info.lookup_geometry_validation,
        )

    @staticmethod
    def _geometry_source(region: Region) -> SourceReference:
        return SourceReference(
            name=region.geometry_source,
            version=region.geometry_source_version,
            uri=region.geometry_source_url,
            license=region.geometry_license,
            method=region.geometry_method,
        )

    def _hierarchy_edge(self, child: Region, parent_name: str) -> HierarchyEdge:
        try:
            definition = self._hierarchy_edges[(child.name, parent_name)]
        except KeyError as error:
            raise RegionDataError(
                f"missing hierarchy definition for {child.name} -> {parent_name}"
            ) from error
        return HierarchyEdge(
            child=child.name,
            parent=parent_name,
            origin=definition.origin,
            source=definition.source,
            source_path=definition.source_path,
            cf_version=self._dataset_info.cf_version,
            mapping=self._mapping_reference(),
        )

    def _match(
        self,
        region: Region,
        *,
        relation: str,
        method: str,
        predicate: str,
        source: SourceReference,
        distance_km: float | None = None,
    ) -> RegionMatch:
        return RegionMatch(
            region=region,
            relation=relation,  # type: ignore[arg-type]
            cf_version=self._dataset_info.cf_version,
            mapping=self._mapping_reference(),
            method=method,
            predicate=predicate,
            source=source,
            distance_km=distance_km,
        )

    def match(
        self,
        *,
        longitude: object,
        latitude: object,
        section_tolerance_km: object = 0.0,
        include_ancestors: bool = True,
    ) -> tuple[RegionMatch, ...]:
        """Return all direct and hierarchical region matches for a WGS84 point."""

        checked_longitude, checked_latitude = validate_coordinates(
            longitude=longitude,
            latitude=latitude,
        )
        tolerance = validate_section_tolerance(section_tolerance_km)
        if not isinstance(include_ancestors, bool):
            raise CoordinateError("include_ancestors must be a boolean")
        query_longitude = -180.0 if checked_longitude == 180.0 else checked_longitude
        point = Point(query_longitude, checked_latitude)

        direct: dict[int, RegionMatch] = {}
        candidate_indexes = self._tree.query(point)
        for raw_index in candidate_indexes:
            index = int(raw_index)
            region = self._regions[index]
            if region.kind == "area" and self._lookup_store.geometry(
                region.name
            ).covers(point):
                direct[index] = self._match(
                    region,
                    relation="covered_by",
                    method="polygon_lookup",
                    predicate="covers",
                    source=self._geometry_source(region),
                )

        if tolerance > 0.0:
            for index in self._section_indexes:
                distance = _line_distance_km(
                    self._lookup_store.geometry(self._regions[index].name),
                    longitude=query_longitude,
                    latitude=checked_latitude,
                )
                if distance <= tolerance:
                    region = self._regions[index]
                    direct[index] = self._match(
                        region,
                        relation="near_section",
                        method=self._dataset_info.section_method,
                        predicate="distance_lte",
                        source=self._geometry_source(region),
                        distance_km=distance,
                    )

        matches_by_name = {match.name: match for match in direct.values()}
        if include_ancestors:
            pending = deque(matches_by_name)
            while pending:
                child_name = pending.popleft()
                child = self._regions[self._name_to_index[child_name]]
                for parent_name in child.parents:
                    if parent_name in matches_by_name:
                        continue
                    parent = self._regions[self._name_to_index[parent_name]]
                    matches_by_name[parent_name] = self._match(
                        parent,
                        relation="ancestor",
                        method="hierarchy_expansion",
                        predicate="broader",
                        source=self._hierarchy_edge(child, parent_name).source,
                    )
                    pending.append(parent_name)

        relation_order = {"covered_by": 0, "near_section": 0, "ancestor": 1}
        return tuple(
            sorted(
                matches_by_name.values(),
                key=lambda match: (
                    -match.region.specificity,
                    relation_order[match.relation],
                    match.name,
                ),
            )
        )
