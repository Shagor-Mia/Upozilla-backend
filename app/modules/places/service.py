import uuid

from fastapi import BackgroundTasks, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core import embeddings, translation
from app.core.content_scope import assert_tenant_match, tenant_scoped
from app.core.dependencies import CurrentUser
from app.core.geo import NearParams, apply_near_paginated
from app.core.pagination import PageParams
from app.core.tenant import resolve_tenant_id
from app.db.models.ai import KnowledgeSourceType
from app.db.models.location import Location
from app.db.models.marketplace import ModerationStatus

from app.db.models.place import Place, PlaceCategory
from app.modules.moderation import service as moderation_service
from app.modules.places.schemas import PlaceCreate, PlaceSubmit, PlaceUpdate


def _assert_location(db: Session, location_id: uuid.UUID) -> None:
    if db.query(Location.id).filter(Location.id == location_id).first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown location")


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
    category: PlaceCategory | None = None,
    near: NearParams | None = None,
    *,
    request: Request | None = None,
) -> tuple[list[tuple[Place, float | None]], int]:
    query = tenant_scoped(
        db.query(Place).filter(Place.status == "published", Place.moderation_status == ModerationStatus.APPROVED.value),
        Place,
        db,
        request=request,
    )
    if location_id is not None:
        query = query.filter(Place.location_id == location_id)
    if featured_only:
        query = query.filter(Place.is_featured.is_(True))
    if category is not None:
        query = query.filter(Place.category == category)
    return apply_near_paginated(query.order_by(Place.name_bn), Place, near or NearParams(), page)


def get_place_by_slug(db: Session, slug: str, *, request: Request | None = None) -> Place:
    query = tenant_scoped(
        db.query(Place).filter(
            Place.slug == slug, Place.status == "published", Place.moderation_status == ModerationStatus.APPROVED.value
        ),
        Place,
        db,
        request=request,
    )
    place = query.first()
    assert_tenant_match(place, db, request=request, detail="place not found")
    return place


def create_place(
    db: Session, payload: PlaceCreate, background_tasks: BackgroundTasks, actor: CurrentUser
) -> Place:
    """Admin/staff form (CONTENT_MANAGE) - published straight away, no queue."""
    place = Place(
        tenant_id=resolve_tenant_id(db, actor),
        moderation_status=ModerationStatus.APPROVED.value,
        **payload.model_dump(),
    )
    db.add(place)
    db.commit()
    db.refresh(place)
    translation.schedule_translations(background_tasks, Place, place.id, ["name", "description"])
    _schedule_reindex(background_tasks, place)
    return place


def submit_place(
    db: Session, payload: PlaceSubmit, background_tasks: BackgroundTasks, actor: CurrentUser
) -> Place:
    """Public form (any logged-in user, POST /places/submit) - always enters
    the moderation queue pending, never auto-approved (product decision)."""
    _assert_location(db, payload.location_id)
    tenant_id = resolve_tenant_id(db, actor)
    place = Place(
        tenant_id=tenant_id,
        location_id=payload.location_id,
        name_bn=payload.name,
        slug=f"place-{uuid.uuid4().hex[:10]}",
        category=payload.category,
        description_bn=payload.description,
        cover_image=payload.gallery[0] if payload.gallery else None,
        gallery=payload.gallery or None,
        latitude=payload.latitude,
        longitude=payload.longitude,
        seller_user_id=actor.uuid,
    )
    db.add(place)
    db.flush()
    moderation_service.enqueue_place(db, place=place, tenant_id=tenant_id)
    db.commit()
    db.refresh(place)
    translation.schedule_translations(background_tasks, Place, place.id, ["name", "description"])
    _schedule_reindex(background_tasks, place)
    return place


def list_mine(db: Session, actor: CurrentUser) -> list[Place]:
    return (
        db.query(Place)
        .filter(Place.seller_user_id == actor.uuid)
        .order_by(Place.created_at.desc())
        .all()
    )
