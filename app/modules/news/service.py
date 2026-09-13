import uuid

from fastapi import BackgroundTasks, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core import embeddings, news_ai
from app.core.content_scope import assert_tenant_match, tenant_scoped
from app.core.dependencies import CurrentUser
from app.core.pagination import PageParams
from app.core.tenant import resolve_tenant_id
from app.db.models.ai import KnowledgeSourceType
from app.db.models.news import NewsArticle, NewsSource
from app.modules.news.schemas import NewsArticleCreate, NewsArticleUpdate


def _schedule_reindex(background_tasks: BackgroundTasks, article: NewsArticle) -> None:
    if article.status != "published":
        return
    text = f"{article.title} {article.summary or ''} {article.body or ''}".strip()
    embeddings.schedule_reindex(background_tasks, KnowledgeSourceType.NEWS, article.id, text, article.tenant_id)


def list_sources(db: Session) -> list[NewsSource]:
    return db.query(NewsSource).filter(NewsSource.active.is_(True)).order_by(NewsSource.name).all()


def list_articles(
    db: Session,
    page: PageParams,
    location_id: uuid.UUID | None = None,
    category: str | None = None,
    *,
    request: Request | None = None,
) -> tuple[list[NewsArticle], int]:
    query = tenant_scoped(db.query(NewsArticle).filter(NewsArticle.status == "published"), NewsArticle, db, request=request)
    if location_id is not None:
        query = query.filter(NewsArticle.location_id == location_id)
    if category is not None:
        query = query.filter(NewsArticle.category == category)
    total = query.count()
    rows = query.order_by(NewsArticle.published_at.desc()).offset(page.offset).limit(page.page_size).all()
    return rows, total


def list_all_for_admin(db: Session, actor: CurrentUser) -> list[NewsArticle]:
    """Admin CMS list (every status, newest first) so a draft can be found and
    published again after creation - the public list only ever shows published."""
    tenant_id = resolve_tenant_id(db, actor)
    query = db.query(NewsArticle)
    if tenant_id:
        query = query.filter(NewsArticle.tenant_id == tenant_id)
    return query.order_by(NewsArticle.created_at.desc()).limit(200).all()


def get_article_by_slug(db: Session, slug: str, *, request: Request | None = None) -> NewsArticle:
    query = tenant_scoped(
        db.query(NewsArticle).filter(NewsArticle.slug == slug, NewsArticle.status == "published"),
        NewsArticle,
        db,
        request=request,
    )
    article = query.first()
    assert_tenant_match(article, db, request=request, detail="article not found")
    return article


def create_article(
    db: Session, payload: NewsArticleCreate, background_tasks: BackgroundTasks, actor: CurrentUser
) -> NewsArticle:
    article = NewsArticle(tenant_id=resolve_tenant_id(db, actor), **payload.model_dump())
    db.add(article)
    db.commit()
    db.refresh(article)
    news_ai.schedule_enrich(background_tasks, article.id)
    _schedule_reindex(background_tasks, article)
    return article


def get_article_for_admin(db: Session, article_id: uuid.UUID, actor: CurrentUser) -> NewsArticle:
    """Any status, tenant-scoped - the admin-edit counterpart to
    `get_article_by_slug`'s public/published-only lookup."""
    tenant_id = resolve_tenant_id(db, actor)
    query = db.query(NewsArticle).filter(NewsArticle.id == article_id)
    if tenant_id:
        query = query.filter(NewsArticle.tenant_id == tenant_id)
    article = query.first()
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="article not found")
    return article


def update_article(
    db: Session,
    article_id: uuid.UUID,
    payload: NewsArticleUpdate,
    background_tasks: BackgroundTasks,
    actor: CurrentUser,
) -> NewsArticle:
    article = get_article_for_admin(db, article_id, actor)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(article, field, value)
    db.commit()
    db.refresh(article)
    _schedule_reindex(background_tasks, article)
    return article
