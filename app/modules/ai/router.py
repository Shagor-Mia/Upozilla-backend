from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_optional_user
from app.core.rate_limit import rate_limit_by_user_or_ip
from app.core.tenant import resolve_tenant_id
from app.modules.ai import service
from app.modules.ai.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    dependencies=[
        Depends(
            rate_limit_by_user_or_ip(
                "ai-chat",
                settings.AI_CHAT_RATE_LIMIT_PER_HOUR,
                settings.AI_CHAT_RATE_LIMIT_PER_HOUR_ANONYMOUS,
                3600,
            )
        )
    ],
)
async def chat(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    viewer: CurrentUser | None = Depends(get_optional_user),
) -> ChatResponse:
    """Public floating widget + the /ask page both hit this. Tenant resolution
    follows the same order as every other public endpoint (app/core/tenant.py):
    the viewer's own tenant if logged in, else an X-Tenant-Slug header, else
    the single active tenant - rag.retrieve additionally matches untenanted
    knowledge chunks either way."""
    tenant_id = resolve_tenant_id(db, viewer, request=request)
    return await service.ask(db, str(tenant_id) if tenant_id else None, payload.message)
