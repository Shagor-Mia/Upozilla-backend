import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.core.pagination import PageParams, Paginated
from app.core.rbac import Permission
from app.core.ws_manager import manager
from app.db.models.moderation import ModerationEntityType, ModerationQueueStatus
from app.modules.moderation import service
from app.modules.moderation.schemas import ModerationQueueItem, ModerationReviewBody, ModerationStats

router = APIRouter(prefix="/moderation", tags=["moderation"])

moderator_required = require_permission(Permission.MARKETPLACE_MODERATE)


@router.get("/queue", response_model=Paginated[ModerationQueueItem])
def list_queue(
    status: ModerationQueueStatus | None = ModerationQueueStatus.PENDING,
    entity_type: ModerationEntityType | None = None,
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
    moderator: CurrentUser = Depends(moderator_required),
) -> Paginated[ModerationQueueItem]:
    items, total = service.list_queue(db, moderator, queue_status=status, entity_type=entity_type, page=page)
    return Paginated(items=items, total=total, page=page.page, page_size=page.page_size)


@router.get("/stats", response_model=ModerationStats)
def stats(db: Session = Depends(get_db), moderator: CurrentUser = Depends(moderator_required)) -> ModerationStats:
    return service.get_stats(db, moderator)


@router.post("/queue/{queue_id}/review", response_model=ModerationQueueItem)
async def review_item(
    queue_id: uuid.UUID,
    payload: ModerationReviewBody,
    db: Session = Depends(get_db),
    moderator: CurrentUser = Depends(moderator_required),
) -> ModerationQueueItem:
    item, dispute = await run_in_threadpool(
        service.review, db, moderator, queue_id, payload.decision, payload.note, payload.favored_party
    )
    if dispute is not None:
        # Local import: only the contract-dispute path needs the contracts
        # module, and importing it lazily here avoids a hard import-time
        # coupling between the moderation and contracts modules.
        from app.modules.contracts import service as contracts_service

        contract_response = await run_in_threadpool(contracts_service.get_response, db, dispute["contract_id"])
        event = {
            "type": "contract_update",
            "event": "dispute_resolved",
            "contract_id": str(dispute["contract_id"]),
            "contract": contract_response.model_dump(mode="json"),
        }
        for user_id in {dispute["employer_user_id"], dispute["worker_user_id"]}:
            if user_id is not None:
                await manager.send_to_user(str(user_id), event)
    return item
