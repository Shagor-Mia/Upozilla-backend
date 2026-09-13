"""Section 8.7 - min-supported-app-version gate.

The mobile app calls this on launch and shows a force-update screen when its
own version is below `min_supported_app_version`. Values come from the admin
settings (DB) with the env defaults as fallback, so an old client can be
retired without a backend deploy.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core import runtime_settings
from app.core.config import settings

router = APIRouter(prefix="/meta", tags=["meta"])


class MetaResponse(BaseModel):
    api_version: str
    min_supported_app_version: str
    latest_app_version: str


@router.get("", response_model=MetaResponse)
def get_meta() -> MetaResponse:
    return MetaResponse(
        api_version=settings.API_V1_PREFIX.rsplit("/", 1)[-1],
        min_supported_app_version=runtime_settings.get("min_supported_app_version")
        or settings.MIN_SUPPORTED_APP_VERSION,
        latest_app_version=runtime_settings.get("latest_app_version") or settings.LATEST_APP_VERSION,
    )
