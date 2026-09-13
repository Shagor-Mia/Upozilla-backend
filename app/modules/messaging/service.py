"""Conversations/messages (Section 5.8) - REST is the write path; the
WebSocket in `router.py` is delivery only. Participant checks happen here on
every read/write (Section 14.3: authorization is per-message, not per-socket)."""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser
from app.core.tenant import resolve_tenant_id
from app.db.models import Conversation, ListingType, Message, User
from app.modules.exchange.lookup import find_listing, get_public_listing
from app.modules.messaging.schemas import (
    ConversationParticipant,
    ConversationResponse,
    MessageResponse,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _message_response(message: Message) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        body=message.body,
        created_at=message.created_at,
        read_at=message.read_at,
    )


def _get_participant_conversation(db: Session, conversation_id: uuid.UUID, user: CurrentUser) -> Conversation:
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conversation is None or user.uuid not in (conversation.buyer_id, conversation.seller_id):
        # 404 rather than 403 so conversation ids can't be probed (Section 14.1 IDOR).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found")
    return conversation


def other_participant_id(conversation: Conversation, user_id: uuid.UUID) -> uuid.UUID:
    return conversation.seller_id if conversation.buyer_id == user_id else conversation.buyer_id


# --- conversations ---------------------------------------------------------------


def get_or_create_conversation(
    db: Session, buyer: CurrentUser, listing_type: ListingType, listing_id: uuid.UUID
) -> Conversation:
    listing = get_public_listing(db, listing_type, listing_id)
    if listing.seller_user_id == buyer.uuid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="you cannot message yourself about your own listing")

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.listing_type == listing_type.value,
            Conversation.listing_id == listing_id,
            Conversation.buyer_id == buyer.uuid,
        )
        .first()
    )
    if conversation is None:
        conversation = Conversation(
            tenant_id=resolve_tenant_id(db, buyer),
            listing_type=listing_type.value,
            listing_id=listing_id,
            buyer_id=buyer.uuid,
            seller_id=listing.seller_user_id,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    return conversation


def _to_conversation_responses(db: Session, rows: list[Conversation], user: CurrentUser) -> list[ConversationResponse]:
    if not rows:
        return []
    user_ids = {r.buyer_id for r in rows} | {r.seller_id for r in rows}
    names = dict(db.query(User.id, User.full_name).filter(User.id.in_(user_ids)).all())
    conversation_ids = [r.id for r in rows]

    unread = dict(
        db.query(Message.conversation_id, func.count(Message.id))
        .filter(
            Message.conversation_id.in_(conversation_ids),
            Message.sender_id != user.uuid,
            Message.read_at.is_(None),
        )
        .group_by(Message.conversation_id)
        .all()
    )

    responses = []
    for row in rows:
        last = (
            db.query(Message)
            .filter(Message.conversation_id == row.id)
            .order_by(Message.created_at.desc())
            .first()
        )
        listing = find_listing(db, ListingType(row.listing_type), row.listing_id)
        buyer = ConversationParticipant(id=row.buyer_id, full_name=names.get(row.buyer_id, ""))
        seller = ConversationParticipant(id=row.seller_id, full_name=names.get(row.seller_id, ""))
        responses.append(
            ConversationResponse(
                id=row.id,
                listing_type=ListingType(row.listing_type),
                listing_id=row.listing_id,
                listing_title=listing.title_bn if listing else None,
                listing_image=(listing.images or [None])[0] if listing else None,
                buyer=buyer,
                seller=seller,
                other_party=seller if row.buyer_id == user.uuid else buyer,
                last_message=_message_response(last) if last else None,
                unread_count=int(unread.get(row.id, 0)),
                created_at=row.created_at,
            )
        )
    return responses


def list_conversations(db: Session, user: CurrentUser) -> list[ConversationResponse]:
    rows = (
        db.query(Conversation)
        .filter(or_(Conversation.buyer_id == user.uuid, Conversation.seller_id == user.uuid))
        .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc())
        .limit(100)
        .all()
    )
    return _to_conversation_responses(db, rows, user)


def get_conversation(db: Session, conversation_id: uuid.UUID, user: CurrentUser) -> ConversationResponse:
    conversation = _get_participant_conversation(db, conversation_id, user)
    return _to_conversation_responses(db, [conversation], user)[0]


# --- messages --------------------------------------------------------------------


def list_messages(db: Session, conversation_id: uuid.UUID, user: CurrentUser, limit: int = 100) -> list[MessageResponse]:
    conversation = _get_participant_conversation(db, conversation_id, user)
    rows = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    # Reading the thread marks the other party's messages as read.
    db.query(Message).filter(
        Message.conversation_id == conversation.id,
        Message.sender_id != user.uuid,
        Message.read_at.is_(None),
    ).update({Message.read_at: _now()}, synchronize_session=False)
    db.commit()
    return [_message_response(m) for m in reversed(rows)]


def send_message(db: Session, conversation_id: uuid.UUID, sender: CurrentUser, body: str) -> tuple[Message, uuid.UUID]:
    """Returns the stored message and the recipient's user id for live delivery."""
    conversation = _get_participant_conversation(db, conversation_id, sender)
    message = Message(conversation_id=conversation.id, sender_id=sender.uuid, body=body)
    conversation.last_message_at = _now()
    db.add(message)
    db.commit()
    db.refresh(message)
    return message, other_participant_id(conversation, sender.uuid)


def unread_total(db: Session, user: CurrentUser) -> int:
    return (
        db.query(func.count(Message.id))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(
            or_(Conversation.buyer_id == user.uuid, Conversation.seller_id == user.uuid),
            Message.sender_id != user.uuid,
            Message.read_at.is_(None),
        )
        .scalar()
        or 0
    )
