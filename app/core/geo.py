"""Section 17 Phase 3 - "near me" queries without PostGIS.

Coordinates are plain float columns (Section 5), so distance is computed with the
haversine formula in SQL. Good enough for an upazila-sized radius; switch to
PostGIS/earthdistance if a national-scale query ever needs an index.
"""

from typing import Any, TypeVar

from fastapi import Query
from sqlalchemy import func
from sqlalchemy.orm import Query as OrmQuery

from app.core.pagination import PageParams

EARTH_RADIUS_KM = 6371.0
DEFAULT_RADIUS_KM = 10.0
MAX_RADIUS_KM = 50.0

T = TypeVar("T")


class NearParams:
    """Optional `?lat=&lng=&radius_km=` on directory list endpoints."""

    def __init__(
        self,
        lat: float | None = Query(None, ge=-90, le=90),
        lng: float | None = Query(None, ge=-180, le=180),
        radius_km: float = Query(DEFAULT_RADIUS_KM, gt=0, le=MAX_RADIUS_KM),
    ):
        self.lat = lat
        self.lng = lng
        self.radius_km = radius_km

    @property
    def enabled(self) -> bool:
        return self.lat is not None and self.lng is not None


def distance_km_expr(model: Any, lat: float, lng: float):
    """SQL expression for the great-circle distance from (lat, lng) to a row."""
    cos_term = (
        func.cos(func.radians(lat))
        * func.cos(func.radians(model.latitude))
        * func.cos(func.radians(model.longitude) - func.radians(lng))
        + func.sin(func.radians(lat)) * func.sin(func.radians(model.latitude))
    )
    # Clamp for floating-point drift so acos() never sees a value > 1.
    return EARTH_RADIUS_KM * func.acos(func.least(1.0, func.greatest(-1.0, cos_term)))


def apply_near(query: OrmQuery, model: Any, near: NearParams) -> list[tuple[Any, float | None]]:
    """Runs `query` and returns (row, distance_km) pairs.

    With coordinates: rows without a location are dropped, the radius filter is
    applied, and results are ordered nearest-first. Without: the caller's own
    ordering is kept and every distance is None.
    """
    if not near.enabled:
        return [(row, None) for row in query.all()]

    distance = distance_km_expr(model, near.lat, near.lng).label("distance_km")
    rows = (
        query.filter(model.latitude.isnot(None), model.longitude.isnot(None))
        .add_columns(distance)
        .filter(distance <= near.radius_km)
        .order_by(None)
        .order_by(distance, model.name_bn)
        .all()
    )
    return [(row, round(float(dist), 1)) for row, dist in rows]


def apply_near_paginated(
    query: OrmQuery, model: Any, near: NearParams, page: PageParams
) -> tuple[list[tuple[Any, float | None]], int]:
    """Same as `apply_near`, but returns a (page_of_rows, total) pair instead of eagerly
    materializing every matching row - for directory list endpoints large enough to need
    real pagination."""
    if not near.enabled:
        total = query.count()
        rows = query.offset(page.offset).limit(page.page_size).all()
        return [(row, None) for row in rows], total

    distance = distance_km_expr(model, near.lat, near.lng).label("distance_km")
    filtered = (
        query.filter(model.latitude.isnot(None), model.longitude.isnot(None))
        .add_columns(distance)
        .filter(distance <= near.radius_km)
    )
    total = filtered.count()
    rows = (
        filtered.order_by(None)
        .order_by(distance, model.name_bn)
        .offset(page.offset)
        .limit(page.page_size)
        .all()
    )
    return [(row, round(float(dist), 1)) for row, dist in rows], total


def with_distance(response: T, distance_km: float | None) -> T:
    """Attaches the computed distance to an already-built response model."""
    return response.model_copy(update={"distance_km": distance_km})  # type: ignore[attr-defined]
