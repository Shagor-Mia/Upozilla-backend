import uuid

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import User
from app.modules.auth.phone import normalize_bd_phone
from app.modules.users.schemas import UserLookupResponse, UserProfileResponse, UserProfileUpdate


def update_profile(db: Session, user_id: uuid.UUID, payload: UserProfileUpdate) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    changes = payload.model_dump(exclude_unset=True)

    if "email" in changes and changes["email"] and changes["email"].lower() != (user.email or "").lower():
        if db.query(User).filter(func.lower(User.email) == changes["email"].lower(), User.id != user_id).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already in use")

    if "phone" in changes and changes["phone"] != user.phone:
        if changes["phone"] and db.query(User).filter(User.phone == changes["phone"], User.id != user_id).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="phone already in use")
        # A changed number is unverified until the OTP flow confirms it again -
        # otherwise the Section 5.8 write-gate could be carried over to any number.
        user.phone_verified_at = None

    for field, value in changes.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


def lookup_by_phone(db: Session, raw_phone: str) -> UserLookupResponse:
    """Section 1's "Ownership constraint": resolves a phone number to an
    existing active user, for the create-contract screen to name a worker
    without a separate invite flow."""
    try:
        phone = normalize_bd_phone(raw_phone)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    user = db.query(User).filter(User.phone == phone, User.status == "active").first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no user found with that phone number")
    return UserLookupResponse(id=user.id, full_name=user.full_name)


def to_profile_response(user: User) -> UserProfileResponse:
    return UserProfileResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        status=user.status,
        phone_verified=user.phone_verified_at is not None,
    )
