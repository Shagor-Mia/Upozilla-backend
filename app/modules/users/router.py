from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, require_phone_verified
from app.core.rate_limit import rate_limit_by_user
from app.modules.users import service
from app.modules.users.schemas import UserLookupResponse, UserProfileResponse, UserProfileUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserProfileResponse)
def update_my_profile(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> UserProfileResponse:
    user = service.update_profile(db, current_user.uuid, payload)
    return service.to_profile_response(user)


@router.get(
    "/lookup",
    response_model=UserLookupResponse,
    dependencies=[Depends(rate_limit_by_user("user-lookup", settings.USER_LOOKUP_PER_USER_PER_MINUTE, 60))],
)
def lookup_user(
    phone: str,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_phone_verified),
) -> UserLookupResponse:
    return service.lookup_by_phone(db, phone)
