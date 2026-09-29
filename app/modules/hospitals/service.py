import uuid

from fastapi import BackgroundTasks, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core import embeddings, translation
from app.core.content_scope import assert_tenant_match, tenant_scoped
from app.core.dependencies import CurrentUser
from app.core.geo import NearParams, apply_near_paginated
from app.core.location_scope import assert_location_in_tenant
from app.core.pagination import PageParams
from app.core.rbac import Permission
from app.core.tenant import resolve_tenant_id
from app.db.models.ai import KnowledgeSourceType

from app.db.models.hospital import Doctor, Hospital
from app.db.models.location import Location
from app.modules.hospitals.schemas import DoctorCreate, HospitalCreate, HospitalUpdate


def _assert_location(db: Session, location_id: uuid.UUID, tenant_id: uuid.UUID | None) -> None:
    if db.query(Location.id).filter(Location.id == location_id).first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown location")
    assert_location_in_tenant(db, location_id, tenant_id)


def _schedule_reindex(background_tasks: BackgroundTasks, hospital: Hospital) -> None:
    # Hospitals have no status column (Section 17 Phase 1) - always public.
    text = f"{hospital.name_bn} {hospital.name_en or ''} {hospital.address or ''}".strip()
    embeddings.schedule_reindex(
        background_tasks, KnowledgeSourceType.HOSPITAL, hospital.id, text, hospital.tenant_id
    )


def _assert_can_manage(hospital: Hospital, actor: CurrentUser) -> None:
    """A hospital-manager (Permission.CONTENT_MANAGE absent) may only touch the
    one hospital they own; staff with CONTENT_MANAGE can touch any of them."""
    if actor.has_permission(Permission.CONTENT_MANAGE):
        return
    if not actor.can_manage_hospital or hospital.owner_user_id != actor.uuid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")


def update_hospital(
    db: Session, hospital_id, payload: HospitalUpdate, background_tasks: BackgroundTasks, actor: CurrentUser
) -> Hospital:
    hospital = get_hospital(db, hospital_id, actor)
    _assert_can_manage(hospital, actor)
    changes = payload.model_dump(exclude_unset=True)
    if "location_id" in changes and changes["location_id"] is not None:
        _assert_location(db, changes["location_id"], hospital.tenant_id or resolve_tenant_id(db, actor))
    for field, value in changes.items():
        setattr(hospital, field, value)
    db.commit()
    db.refresh(hospital)
    translation.schedule_translations(background_tasks, Hospital, hospital.id, ["name"])
    _schedule_reindex(background_tasks, hospital)
    return hospital


def list_hospitals(
    db: Session,
    page: PageParams,
    location_id: uuid.UUID | None = None,
    near: NearParams | None = None,
    *,
    request: Request | None = None,
) -> tuple[list[tuple[Hospital, float | None]], int]:
    query = tenant_scoped(db.query(Hospital), Hospital, db, request=request)
    if location_id is not None:
        query = query.filter(Hospital.location_id == location_id)
    return apply_near_paginated(query.order_by(Hospital.name_bn), Hospital, near or NearParams(), page)


def get_hospital(
    db: Session, hospital_id: uuid.UUID, actor: CurrentUser | None = None, *, request: Request | None = None
) -> Hospital:
    """Tenant match is enforced either way - see markets.service.get_market."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    assert_tenant_match(hospital, db, actor=actor, request=request, detail="hospital not found")
    return hospital


def create_hospital(
    db: Session, payload: HospitalCreate, background_tasks: BackgroundTasks, actor: CurrentUser
) -> Hospital:
    owner_user_id = None
    if not actor.has_permission(Permission.CONTENT_MANAGE):
        if not actor.can_manage_hospital:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
        already_owns = db.query(Hospital).filter(Hospital.owner_user_id == actor.uuid).first()
        if already_owns is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="you already manage a hospital")
        owner_user_id = actor.uuid

    tenant_id = resolve_tenant_id(db, actor)
    _assert_location(db, payload.location_id, tenant_id)
    hospital = Hospital(tenant_id=tenant_id, owner_user_id=owner_user_id, **payload.model_dump())
    db.add(hospital)
    db.commit()
    db.refresh(hospital)
    translation.schedule_translations(background_tasks, Hospital, hospital.id, ["name"])
    _schedule_reindex(background_tasks, hospital)
    return hospital


def list_ambulance_hospitals(db: Session, *, request: Request | None = None) -> list[Hospital]:
    query = tenant_scoped(db.query(Hospital), Hospital, db, request=request)
    return query.filter(Hospital.ambulance_contact.isnot(None)).order_by(Hospital.name_bn).all()


def get_my_hospital(db: Session, actor: CurrentUser) -> Hospital | None:
    return db.query(Hospital).filter(Hospital.owner_user_id == actor.uuid).first()


def list_doctors(db: Session, hospital_id: uuid.UUID, *, request: Request | None = None) -> list[Doctor]:
    # 404s on a cross-tenant hospital_id the same way create_doctor already does,
    # instead of leaking another tenant's doctor roster through a direct hospital_id.
    get_hospital(db, hospital_id, request=request)
    return db.query(Doctor).filter(Doctor.hospital_id == hospital_id).order_by(Doctor.name).all()


def create_doctor(db: Session, payload: DoctorCreate, actor: CurrentUser) -> Doctor:
    # Verifies the hospital exists and belongs to the actor's tenant before
    # attaching a doctor to it - previously accepted any hospital_id with no
    # existence check at all.
    hospital = get_hospital(db, payload.hospital_id, actor)
    _assert_can_manage(hospital, actor)
    doctor = Doctor(**payload.model_dump())
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor
