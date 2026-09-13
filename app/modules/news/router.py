import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.core.pagination import PageParams, Paginated
from app.core.rbac import Permission
from app.modules.news import service
from app.modules.news.schemas import (
    NewsArticleCreate,
    NewsArticleDetailResponse,
    NewsArticleResponse,
    NewsSourceResponse,
)

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=Paginated[NewsArticleResponse])
def list_articles(
    request: Request,
    location_id: uuid.UUID | None = None,
    category: str | None = None,
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
) -> Paginated[NewsArticleResponse]:
    articles, total = service.list_articles(db, page, location_id=location_id, category=category, request=request)
    return Paginated(
        items=[NewsArticleResponse.model_validate(a) for a in articles],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/sources", response_model=list[NewsSourceResponse])
def list_sources(db: Session = Depends(get_db)) -> list[NewsSourceResponse]:
    return [NewsSourceResponse.model_validate(s) for s in service.list_sources(db)]


@router.get("/all", response_model=list[NewsArticleResponse])
def all_articles_for_admin(
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.NEWS_MANAGE, Permission.CONTENT_MANAGE)),
) -> list[NewsArticleResponse]:
    """Admin CMS list (every status, newest first). Registered before
    `/{slug}` - a path param route would otherwise shadow this and swallow
    every request here as a (nonexistent) article lookup for slug="all"."""
    return [NewsArticleResponse.model_validate(a) for a in service.list_all_for_admin(db, actor)]


@router.get("/{slug}", response_model=NewsArticleDetailResponse)
def get_article(slug: str, request: Request, db: Session = Depends(get_db)) -> NewsArticleDetailResponse:
    return NewsArticleDetailResponse.model_validate(service.get_article_by_slug(db, slug, request=request))


@router.post("", response_model=NewsArticleResponse, status_code=201)
def create_article(
    payload: NewsArticleCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.NEWS_MANAGE, Permission.CONTENT_MANAGE)),
) -> NewsArticleResponse:
    return NewsArticleResponse.model_validate(service.create_article(db, payload, background_tasks, actor))
