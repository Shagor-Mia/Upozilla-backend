import asyncio
import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, require_phone_verified
from app.core.rate_limit import rate_limit_by_user
from app.core.ws_manager import manager
from app.modules.auth import service as auth_service
from app.modules.messaging import service
from app.modules.messaging.schemas import (
    ConversationCreate,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
    UnreadCountResponse,
)

router = APIRouter(prefix="/conversations", tags=["messaging"])
ws_router = APIRouter(tags=["messaging"])


@router.get("", response_model=list[ConversationResponse])
def list_conversations(
    db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)
) -> list[ConversationResponse]:
    return service.list_conversations(db, current_user)


@router.get("/unread-count", response_model=UnreadCountResponse)
def unread_count(
    db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)
) -> UnreadCountResponse:
    return UnreadCountResponse(unread=service.unread_total(db, current_user))


@router.post("", response_model=ConversationResponse, status_code=201)
def start_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    buyer: CurrentUser = Depends(require_phone_verified),
) -> ConversationResponse:
    conversation = service.get_or_create_conversation(db, buyer, payload.listing_type, payload.listing_id)
    return service.get_conversation(db, conversation.id, buyer)


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ConversationResponse:
    return service.get_conversation(db, conversation_id, current_user)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
def list_messages(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[MessageResponse]:
    return service.list_messages(db, conversation_id, current_user)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=201,
    dependencies=[Depends(rate_limit_by_user("messages", settings.MESSAGES_PER_USER_PER_MINUTE, 60))],
)
async def send_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    sender: CurrentUser = Depends(require_phone_verified),
) -> MessageResponse:
    message, recipient_id = await run_in_threadpool(service.send_message, db, conversation_id, sender, payload.body)
    response = MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        body=message.body,
        created_at=message.created_at,
        read_at=message.read_at,
    )
    # Live delivery to the other participant only - the server decides the
    # recipient from the conversation row, never from the client payload.
    await manager.send_to_user(str(recipient_id), {"type": "message", "message": response.model_dump(mode="json")})
    return response


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, ticket: str) -> None:
    """Authenticated via a single-use ticket (see `/auth/ws-ticket`). The socket is
    closed when the access token that minted the ticket expires (Section 14.3)."""
    resolved = await run_in_threadpool(auth_service.consume_ws_ticket, ticket)
    if resolved is None:
        await websocket.close(code=4401)
        return
    user_id, expires_at = resolved

    await manager.connect(user_id, websocket)

    async def close_on_expiry() -> None:
        await asyncio.sleep(manager.seconds_until(expires_at))
        await websocket.close(code=4403)

    expiry_task = asyncio.create_task(close_on_expiry())
    try:
        while True:
            # Clients only send keep-alive pings; message writes go through REST.
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 - closing on any transport error is the intent
        pass
    finally:
        expiry_task.cancel()
        await manager.disconnect(user_id, websocket)
