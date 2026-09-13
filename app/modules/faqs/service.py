from fastapi import BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.core import embeddings, translation
from app.core.content_scope import assert_tenant_match, tenant_scoped
from app.core.dependencies import CurrentUser
from app.core.tenant import resolve_tenant_id
from app.db.models.ai import KnowledgeSourceType
from app.db.models.faq import Faq
from app.modules.faqs.schemas import FaqCreate, FaqUpdate


def _schedule_reindex(background_tasks: BackgroundTasks, faq: Faq) -> None:
    text = f"{faq.question_bn} {faq.question_en or ''} {faq.answer_bn} {faq.answer_en or ''}".strip()
    embeddings.schedule_publish_reindex(background_tasks, faq, KnowledgeSourceType.FAQ, text)


MAX_FAQS_LISTED = 500


def list_faqs(db: Session, *, request: Request | None = None) -> list[Faq]:
    query = tenant_scoped(db.query(Faq).filter(Faq.status == "published"), Faq, db, request=request)
    return query.order_by(Faq.created_at).limit(MAX_FAQS_LISTED).all()


def list_all_for_admin(db: Session, actor: CurrentUser) -> list[Faq]:
    """Admin CMS list (every status, newest first) so a draft can be found and
    published again after creation - the public list only ever shows published."""
    tenant_id = resolve_tenant_id(db, actor)
    query = db.query(Faq)
    if tenant_id:
        query = query.filter(Faq.tenant_id == tenant_id)
    return query.order_by(Faq.created_at.desc()).limit(MAX_FAQS_LISTED).all()


def get_faq_by_id(db: Session, faq_id, actor: CurrentUser | None = None) -> Faq:
    """`actor` is only passed by authenticated admin call sites - see
    markets.service.get_market for why the public GET omits it."""
    faq = db.query(Faq).filter(Faq.id == faq_id).first()
    assert_tenant_match(faq, db, actor=actor, detail="faq not found")
    return faq


def create_faq(db: Session, payload: FaqCreate, background_tasks: BackgroundTasks, actor: CurrentUser) -> Faq:
    faq = Faq(tenant_id=resolve_tenant_id(db, actor), **payload.model_dump())
    db.add(faq)
    db.commit()
    db.refresh(faq)
    translation.schedule_translations(background_tasks, Faq, faq.id, ["question", "answer"])
    _schedule_reindex(background_tasks, faq)
    return faq


def update_faq(
    db: Session, faq_id, payload: FaqUpdate, background_tasks: BackgroundTasks, actor: CurrentUser
) -> Faq:
    faq = get_faq_by_id(db, faq_id, actor)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(faq, field, value)
    db.commit()
    db.refresh(faq)
    translation.schedule_translations(background_tasks, Faq, faq.id, ["question", "answer"])
    _schedule_reindex(background_tasks, faq)
    return faq
