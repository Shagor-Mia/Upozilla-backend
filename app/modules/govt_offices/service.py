import uuid

from fastapi import BackgroundTasks, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core import translation
from app.core.content_scope import assert_tenant_match, tenant_scoped
from app.core.dependencies import CurrentUser
from app.core.location_scope import assert_location_in_tenant
from app.core.tenant import resolve_tenant_id
from app.db.models.govt_office import GovtOffice
from app.db.models.location import Location
from app.modules.govt_offices.schemas import GovtOfficeCreate, GovtOfficeUpdate


def _assert_location(db: Session, location_id: uuid.UUID, tenant_id: uuid.UUID | None) -> None:
    if db.query(Location.id).filter(Location.id == location_id).first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown location")
    assert_location_in_tenant(db, location_id, tenant_id)


def list_offices(
    db: Session,
    location_id: uuid.UUID | None = None,
    category: str | None = None,
    *,
    request: Request | None = None,
) -> list[GovtOffice]:
    query = tenant_scoped(db.query(GovtOffice), GovtOffice, db, request=request)
    if location_id is not None:
        query = query.filter(GovtOffice.location_id == location_id)
    if category is not None:
        query = query.filter(GovtOffice.category == category)
    return query.order_by(GovtOffice.sort_order, GovtOffice.name_bn).all()


def get_office(
    db: Session, office_id: uuid.UUID, actor: CurrentUser | None = None, *, request: Request | None = None
) -> GovtOffice:
    office = db.query(GovtOffice).filter(GovtOffice.id == office_id).first()
    assert_tenant_match(office, db, actor=actor, request=request, detail="office not found")
    return office


def create_office(
    db: Session, payload: GovtOfficeCreate, background_tasks: BackgroundTasks, actor: CurrentUser
) -> GovtOffice:
    tenant_id = resolve_tenant_id(db, actor)
    _assert_location(db, payload.location_id, tenant_id)
    office = GovtOffice(tenant_id=tenant_id, **payload.model_dump())
    db.add(office)
    db.commit()
    db.refresh(office)
    translation.schedule_translations(background_tasks, GovtOffice, office.id, ["name"])
    return office


def update_office(
    db: Session, office_id: uuid.UUID, payload: GovtOfficeUpdate, background_tasks: BackgroundTasks, actor: CurrentUser
) -> GovtOffice:
    office = get_office(db, office_id, actor)
    changes = payload.model_dump(exclude_unset=True)
    if "location_id" in changes and changes["location_id"] is not None:
        _assert_location(db, changes["location_id"], office.tenant_id or resolve_tenant_id(db, actor))
    for field, value in changes.items():
        setattr(office, field, value)
    db.commit()
    db.refresh(office)
    translation.schedule_translations(background_tasks, GovtOffice, office.id, ["name"])
    return office
