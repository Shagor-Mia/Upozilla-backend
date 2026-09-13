import uuid
from collections.abc import Iterable

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.core import translation
from app.core.dependencies import CurrentUser
from app.core.i18n import localized_value
from app.core.pagination import PageParams
from app.core.tenant import resolve_tenant_id
from app.db.models import Location, Representative, RepresentativeStatus, User
from app.modules.representatives.schemas import (
    RepresentativeAdminUpdate,
    RepresentativeCreate,
    RepresentativeResponse,
    to_response,
)

_SELF_SERVICE_FIELDS = {"bio", "photo_url"}


def to_responses(db: Session, reps: Iterable[Representative], locale: str) -> list[RepresentativeResponse]:
    rows = list(reps)
    if not rows:
        return []
    users = {u.id: u for u in db.query(User).filter(User.id.in_({r.user_id for r in rows})).all()}
    locations = {
        loc.id: localized_value(loc.name_bn, loc.name_en, loc.name_ar, locale)
        for loc in db.query(Location).filter(Location.id.in_({r.location_id for r in rows})).all()
    }
    responses = []
    for r in rows:
        user = users.get(r.user_id)
        if user is None:
            continue
        responses.append(
            to_response(
                r,
                full_name=user.full_name,
                phone=user.phone,
                location_name=locations.get(r.location_id, ""),
                locale=locale,
            )
        )
    return responses


def list_public(
    db: Session, *, location_id: uuid.UUID | None, position: str | None, page: PageParams
) -> tuple[list[Representative], int]:
    query = db.query(Representative).filter(Representative.status == RepresentativeStatus.ACTIVE.value)
    if location_id is not None:
        query = query.filter(Representative.location_id == location_id)
    if position is not None:
        query = query.filter(Representative.position == position)
    total = query.count()
    rows = query.order_by(Representative.created_at.desc()).offset(page.offset).limit(page.page_size).all()
    return rows, total


def list_mine(db: Session, user_id: uuid.UUID) -> list[Representative]:
    return (
        db.query(Representative)
        .filter(Representative.user_id == user_id)
        .order_by(Representative.created_at.desc())
        .all()
    )


def get_one(db: Session, rep_id: uuid.UUID) -> Representative:
    rep = db.query(Representative).filter(Representative.id == rep_id).first()
    if rep is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="representative not found")
    return rep


def _assert_no_active_duplicate(
    db: Session, location_id: uuid.UUID, position: str, exclude_id: uuid.UUID | None = None
) -> None:
    query = db.query(Representative.id).filter(
        Representative.location_id == location_id,
        Representative.position == position,
        Representative.status == RepresentativeStatus.ACTIVE.value,
    )
    if exclude_id is not None:
        query = query.filter(Representative.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="this position is already held for this location")


def create(
    db: Session, actor: CurrentUser, payload: RepresentativeCreate, background_tasks: BackgroundTasks
) -> Representative:
    if db.query(Location.id).filter(Location.id == payload.location_id).first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown location")
    if db.query(User.id).filter(User.id == payload.user_id).first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown user")
    _assert_no_active_duplicate(db, payload.location_id, payload.position.value)

    rep = Representative(
        tenant_id=resolve_tenant_id(db, actor),
        user_id=payload.user_id,
        location_id=payload.location_id,
        position=payload.position.value,
        bio_bn=payload.bio,
        photo_url=payload.photo_url,
    )
    db.add(rep)
    db.commit()
    db.refresh(rep)
    translation.schedule_translations(background_tasks, Representative, rep.id, ["bio"])
    return rep


def update(
    db: Session,
    actor: CurrentUser,
    rep_id: uuid.UUID,
    payload: RepresentativeAdminUpdate,
    background_tasks: BackgroundTasks,
    *,
    is_admin: bool,
) -> Representative:
    """`is_admin` (CONTENT_MANAGE) may reassign location/position/status; anyone
    else may only touch their own record's bio/photo_url (app/modules/representatives/router.py)."""
    rep = get_one(db, rep_id)
    if not is_admin and rep.user_id != actor.uuid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your representative profile")

    changes = payload.model_dump(exclude_unset=True)
    if not is_admin:
        restricted = set(changes) - _SELF_SERVICE_FIELDS
        if restricted:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"cannot change: {', '.join(sorted(restricted))}")
    else:
        if "position" in changes and changes["position"] is not None:
            changes["position"] = changes["position"].value
        if "status" in changes and changes["status"] is not None:
            changes["status"] = changes["status"].value
        if "location_id" in changes or "position" in changes:
            _assert_no_active_duplicate(
                db,
                changes.get("location_id", rep.location_id),
                changes.get("position", rep.position),
                exclude_id=rep.id,
            )

    field_map = {"bio": "bio_bn"}
    for field, value in changes.items():
        setattr(rep, field_map.get(field, field), value)

    db.commit()
    db.refresh(rep)
    if "bio" in changes:
        translation.schedule_translations(background_tasks, Representative, rep.id, ["bio"])
    return rep
