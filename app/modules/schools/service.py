import uuid

from fastapi import BackgroundTasks, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core import embeddings, translation
from app.core.content_scope import assert_tenant_match, tenant_scoped
from app.core.dependencies import CurrentUser
from app.core.geo import NearParams, apply_near_paginated
from app.core.pagination import PageParams
from app.core.rbac import Permission
from app.core.tenant import resolve_tenant_id
from app.db.models.ai import KnowledgeSourceType
from app.db.models.school import School
from app.modules.schools.schemas import SchoolCreate, SchoolUpdate


def _schedule_reindex(background_tasks: BackgroundTasks, school: School) -> None:
    # Schools have no status column, same as hospitals/govt_offices - always public.
    text = f"{school.name_bn} {school.name_en or ''} {school.address or ''}".strip()
    embeddings.schedule_reindex(background_tasks, KnowledgeSourceType.SCHOOL, school.id, text, school.tenant_id)


def list_schools(
    db: Session,
    page: PageParams,
    location_id: uuid.UUID | None = None,
    near: NearParams | None = None,
    *,
    request: Request | None = None,
) -> tuple[list[tuple[School, float | None]], int]:
    query = tenant_scoped(db.query(School), School, db, request=request)
    if location_id is not None:
        query = query.filter(School.location_id == location_id)
    return apply_near_paginated(query.order_by(School.name_bn), School, near or NearParams(), page)


def get_school(
    db: Session, school_id: uuid.UUID, actor: CurrentUser | None = None, *, request: Request | None = None
) -> School:
    """Tenant match is enforced either way - see markets.service.get_market."""
    school = db.query(School).filter(School.id == school_id).first()
    assert_tenant_match(school, db, actor=actor, request=request, detail="school not found")
    return school


def _assert_can_manage(school: School, actor: CurrentUser) -> None:
    """A school-manager (Permission.CONTENT_MANAGE absent) may only touch the
    one school they own; staff with CONTENT_MANAGE can touch any of them."""
    if actor.has_permission(Permission.CONTENT_MANAGE):
        return
    if not actor.can_manage_school or school.owner_user_id != actor.uuid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")


def create_school(db: Session, payload: SchoolCreate, background_tasks: BackgroundTasks, actor: CurrentUser) -> School:
    owner_user_id = None
    if not actor.has_permission(Permission.CONTENT_MANAGE):
        if not actor.can_manage_school:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
        already_owns = db.query(School).filter(School.owner_user_id == actor.uuid).first()
        if already_owns is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="you already manage a school")
        owner_user_id = actor.uuid

    school = School(tenant_id=resolve_tenant_id(db, actor), owner_user_id=owner_user_id, **payload.model_dump())
    db.add(school)
    db.commit()
    db.refresh(school)
    translation.schedule_translations(background_tasks, School, school.id, ["name"])
    _schedule_reindex(background_tasks, school)
    return school


def update_school(
    db: Session, school_id: uuid.UUID, payload: SchoolUpdate, background_tasks: BackgroundTasks, actor: CurrentUser
) -> School:
    school = get_school(db, school_id, actor)
    _assert_can_manage(school, actor)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(school, field, value)
    db.commit()
    db.refresh(school)
    translation.schedule_translations(background_tasks, School, school.id, ["name"])
    _schedule_reindex(background_tasks, school)
    return school


def get_my_school(db: Session, actor: CurrentUser) -> School | None:
    return db.query(School).filter(School.owner_user_id == actor.uuid).first()
