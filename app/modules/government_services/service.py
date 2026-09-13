import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.core import embeddings, translation
from app.core.content_scope import assert_tenant_match, tenant_scoped
from app.core.dependencies import CurrentUser
from app.core.pagination import PageParams
from app.core.tenant import resolve_tenant_id
from app.db.models.ai import KnowledgeSourceType
from app.db.models.service import LicenseApplication, Service, ServiceCategory
from app.modules.government_services.schemas import LicenseApplicationCreate, ServiceCreate, ServiceUpdate


def _schedule_reindex(background_tasks: BackgroundTasks, svc: Service) -> None:
    text = (
        f"{svc.name_bn} {svc.name_en or ''} {svc.description_bn or ''} {svc.description_en or ''} "
        f"{svc.office_name_bn or ''}"
    ).strip()
    embeddings.schedule_publish_reindex(background_tasks, svc, KnowledgeSourceType.SERVICE, text)


def list_categories(db: Session) -> list[ServiceCategory]:
    return db.query(ServiceCategory).order_by(ServiceCategory.name_bn).all()


def list_services(
    db: Session,
    page: PageParams,
    location_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    *,
    request: Request | None = None,
) -> tuple[list[Service], int]:
    query = tenant_scoped(db.query(Service).filter(Service.status == "published"), Service, db, request=request)
    if location_id is not None:
        query = query.filter(Service.location_id == location_id)
    if category_id is not None:
        query = query.filter(Service.category_id == category_id)
    total = query.count()
    rows = query.order_by(Service.name_bn).offset(page.offset).limit(page.page_size).all()
    return rows, total


def get_service(db: Session, service_id: uuid.UUID, *, request: Request | None = None) -> Service:
    query = tenant_scoped(
        db.query(Service).filter(Service.id == service_id, Service.status == "published"), Service, db, request=request
    )
    svc = query.first()
    assert_tenant_match(svc, db, request=request, detail="service not found")
    return svc


def create_service(
    db: Session, payload: ServiceCreate, background_tasks: BackgroundTasks, actor: CurrentUser
) -> Service:
    svc = Service(tenant_id=resolve_tenant_id(db, actor), **payload.model_dump())
    db.add(svc)
    db.commit()
    db.refresh(svc)
    translation.schedule_translations(background_tasks, Service, svc.id, ["name", "description", "office_name"])
    _schedule_reindex(background_tasks, svc)
    return svc


def get_service_by_id(db: Session, service_id, actor: CurrentUser | None = None) -> Service:
    """`actor` is only passed by authenticated admin call sites - see
    markets.service.get_market for why the public GET omits it."""
    svc = db.query(Service).filter(Service.id == service_id).first()
    assert_tenant_match(svc, db, actor=actor, detail="service not found")
    return svc


def update_service(
    db: Session, service_id, payload: ServiceUpdate, background_tasks: BackgroundTasks, actor: CurrentUser
) -> Service:
    svc = get_service_by_id(db, service_id, actor)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(svc, field, value)
    db.commit()
    db.refresh(svc)
    translation.schedule_translations(background_tasks, Service, svc.id, ["name", "description", "office_name"])
    _schedule_reindex(background_tasks, svc)
    return svc


def create_license_application(
    db: Session, user_id: uuid.UUID, payload: LicenseApplicationCreate
) -> LicenseApplication:
    application = LicenseApplication(
        user_id=user_id,
        submitted_at=datetime.now(timezone.utc),
        **payload.model_dump(),
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


def list_my_applications(db: Session, user_id: uuid.UUID) -> list[LicenseApplication]:
    return (
        db.query(LicenseApplication)
        .filter(LicenseApplication.user_id == user_id)
        .order_by(LicenseApplication.submitted_at.desc())
        .all()
    )
