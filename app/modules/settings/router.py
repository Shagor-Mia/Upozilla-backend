from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core import embeddings, translation
from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.core.rbac import Permission
from app.modules.settings import service
from app.modules.settings.schemas import (
    AdminSettingItem,
    AiSettingsResponse,
    PublicSettings,
    QueuedResponse,
    SettingsUpdate,
    TestConnectionRequest,
    TestConnectionResponse,
)

router = APIRouter(prefix="/settings", tags=["settings"])
admin_router = APIRouter(prefix="/admin/settings", tags=["admin"])

settings_manage = require_permission(Permission.SETTINGS_MANAGE)


@router.get("/public", response_model=PublicSettings)
def public_settings() -> PublicSettings:
    return service.get_public_settings()


@admin_router.get("", response_model=list[AdminSettingItem])
def list_settings(db: Session = Depends(get_db), _: CurrentUser = Depends(settings_manage)) -> list[AdminSettingItem]:
    return service.list_admin_settings(db)


@admin_router.put("", response_model=list[AdminSettingItem])
def update_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(settings_manage),
) -> list[AdminSettingItem]:
    return service.update_settings(db, actor, payload)


@admin_router.post("/translate-missing-content", status_code=202, response_model=QueuedResponse)
def translate_missing_content(
    background_tasks: BackgroundTasks, _: CurrentUser = Depends(settings_manage)
) -> QueuedResponse:
    """Sweeps existing content for blank en/ar fields and queues background
    translation for them. No-op (still 202) unless translation_mode=automatic
    and an OpenAI key is configured."""
    translation.queue_missing_content_translations(background_tasks)
    return QueuedResponse(status="queued")


@admin_router.post("/reindex-knowledge-base", status_code=202, response_model=QueuedResponse)
def reindex_knowledge_base(
    background_tasks: BackgroundTasks, _: CurrentUser = Depends(settings_manage)
) -> QueuedResponse:
    """One-off backfill: re-embeds every existing published place/service/
    hospital/market/news/faq into `knowledge_chunks` (Section 5.13/17 Phase
    4). No-op (still 202) unless an OpenAI key is configured."""
    embeddings.queue_reindex_all(background_tasks)
    return QueuedResponse(status="queued")


@admin_router.get("/ai", response_model=AiSettingsResponse)
def get_ai_settings(db: Session = Depends(get_db), _: CurrentUser = Depends(settings_manage)) -> AiSettingsResponse:
    return service.get_ai_settings(db)


@admin_router.post("/ai/test-connection", response_model=TestConnectionResponse)
def test_ai_connection(
    payload: TestConnectionRequest,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(settings_manage),
) -> TestConnectionResponse:
    return service.test_ai_connection(db, payload)


@admin_router.post("/ai/disconnect", response_model=AiSettingsResponse)
def disconnect_ai(
    db: Session = Depends(get_db), actor: CurrentUser = Depends(settings_manage)
) -> AiSettingsResponse:
    return service.disconnect_ai(db, actor)
