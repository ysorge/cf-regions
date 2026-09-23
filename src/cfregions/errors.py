"""Domain-specific exceptions."""


class CFRegionsError(Exception):
    """Base exception for the package."""


class CoordinateError(CFRegionsError, ValueError):
    """Raised when a longitude, latitude, or tolerance is invalid."""


class RegionNotFoundError(CFRegionsError, KeyError):
    """Raised when a CF standardized region name is unknown."""


class GeometryResolutionNotFoundError(CFRegionsError, ValueError):
    """Raised when a mapping does not declare the requested rendering resolution."""


class RegionDataError(CFRegionsError, RuntimeError):
    """Raised when the bundled geometry catalog is invalid or unavailable."""


class CFVersionNotFoundError(CFRegionsError, ValueError):
    """Raised when a requested CF Standardized Region List release is unavailable."""


class SpatialProfileNotFoundError(CFRegionsError, ValueError):
    """Raised when a spatial interpretation profile or version is unavailable."""


class SpatialProfileCompatibilityError(CFRegionsError, ValueError):
    """Raised when a profile does not support the selected CF release."""
