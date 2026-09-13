import uuid

from fastapi import BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.core import embeddings, translation
from app.core.content_scope import assert_tenant_match, tenant_scoped
from app.core.dependencies import CurrentUser
from app.core.geo import NearParams, apply_near_paginated
from app.core.pagination import PageParams
from app.core.tenant import resolve_tenant_id
from app.db.models.ai import KnowledgeSourceType

from app.db.models.place import Place
from app.modules.places.schemas import PlaceCreate, PlaceUpdate


def _schedule_reindex(background_tasks: BackgroundTasks, place: Place) -> None:
    text = (
        f"{place.name_bn} {place.name_en or ''} {place.description_bn or ''} {place.description_en or ''}"
    ).strip()
    embeddings.schedule_publish_reindex(background_tasks, place, KnowledgeSourceType.PLACE, text)


def get_place_by_id(
    db: Session, place_id, actor: CurrentUser | None = None, *, request: Request | None = None
) -> Place:
    """Tenant match is enforced either way - see markets.service.get_market."""
    place = db.query(Place).filter(Place.id == place_id).first()
    assert_tenant_match(place, db, actor=actor, request=request, detail="place not found")
    return place


def update_place(
    db: Session, place_id, payload: PlaceUpdate, background_tasks: BackgroundTasks, actor: CurrentUser
) -> Place:
    place = get_place_by_id(db, place_id, actor)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(place, field, value)
    db.commit()
    db.refresh(place)
    translation.schedule_translations(background_tasks, Place, place.id, ["name", "description"])
    _schedule_reindex(background_tasks, place)
    return place


def list_places(
    db: Session,
    page: PageParams,
    location_id: uuid.UUID | None = None,
    featured_only: bool = False,
    near: NearParams | None = None,
    *,
    request: Request | None = None,
) -> tuple[list[tuple[Place, float | None]], int]:
    query = tenant_scoped(db.query(Place).filter(Place.status == "published"), Place, db, request=request)
    if location_id is not None:
        query = query.filter(Place.location_id == location_id)
    if featured_only:
        query = query.filter(Place.is_featured.is_(True))
    return apply_near_paginated(query.order_by(Place.name_bn), Place, near or NearParams(), page)


def get_place_by_slug(db: Session, slug: str, *, request: Request | None = None) -> Place:
    query = tenant_scoped(
        db.query(Place).filter(Place.slug == slug, Place.status == "published"), Place, db, request=request
    )
    place = query.first()
    assert_tenant_match(place, db, request=request, detail="place not found")
    return place


def create_place(
    db: Session, payload: PlaceCreate, background_tasks: BackgroundTasks, actor: CurrentUser
) -> Place:
    place = Place(tenant_id=resolve_tenant_id(db, actor), **payload.model_dump())
    db.add(place)
    db.commit()
    db.refresh(place)
    translation.schedule_translations(background_tasks, Place, place.id, ["name", "description"])
    _schedule_reindex(background_tasks, place)
    return place
