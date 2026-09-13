import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.rbac import AuditLog


def record_audit(
    db: Session,
    actor_user_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Section 14.4: every admin/moderator action is logged. Caller commits."""
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            meta=meta or {},
        )
    )
