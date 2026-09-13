import uuid

from fastapi import BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.core import translation
from app.core.content_scope import assert_tenant_match, tenant_scoped
from app.core.dependencies import CurrentUser
from app.core.geo import NearParams, apply_near
from app.core.tenant import resolve_tenant_id

from app.db.models.business import Business
from app.modules.businesses.schemas import BusinessCreate, BusinessUpdate


def get_business_by_id(db: Session, business_id, actor: CurrentUser | None = None) -> Business:
    """`actor` is only passed by authenticated admin call sites - see
    markets.service.get_market for why the public GET omits it."""
    business = db.query(Business).filter(Business.id == business_id).first()
    assert_tenant_match(business, db, actor=actor, detail="business not found")
    return business


def update_business(
    db: Session, business_id, payload: BusinessUpdate, background_tasks: BackgroundTasks, actor: CurrentUser
) -> Business:
    business = get_business_by_id(db, business_id, actor)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(business, field, value)
    db.commit()
    db.refresh(business)
    translation.schedule_translations(background_tasks, Business, business.id, ["name", "description"])
    return business


MAX_BUSINESSES_LISTED = 500


def list_businesses(
    db: Session,
    location_id: uuid.UUID | None = None,
    near: NearParams | None = None,
    *,
    request: Request | None = None,
) -> list[tuple[Business, float | None]]:
    query = tenant_scoped(db.query(Business).filter(Business.status == "active"), Business, db, request=request)
    if location_id is not None:
        query = query.filter(Business.location_id == location_id)
    query = query.order_by(Business.name_bn).limit(MAX_BUSINESSES_LISTED)
    return apply_near(query, Business, near or NearParams())


def get_business_by_slug(db: Session, slug: str, *, request: Request | None = None) -> Business:
    query = tenant_scoped(
        db.query(Business).filter(Business.slug == slug, Business.status == "active"), Business, db, request=request
    )
    business = query.first()
    assert_tenant_match(business, db, request=request, detail="business not found")
    return business


def create_business(
    db: Session,
    owner_user_id: uuid.UUID,
    payload: BusinessCreate,
    background_tasks: BackgroundTasks,
    actor: CurrentUser,
) -> Business:
    business = Business(owner_user_id=owner_user_id, tenant_id=resolve_tenant_id(db, actor), **payload.model_dump())
    db.add(business)
    db.commit()
    db.refresh(business)
    translation.schedule_translations(background_tasks, Business, business.id, ["name", "description"])
    return business
