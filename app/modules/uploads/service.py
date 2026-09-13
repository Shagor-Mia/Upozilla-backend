import time

import cloudinary.utils
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.modules.uploads.schemas import UploadSignatureResponse


def create_upload_signature(actor: CurrentUser) -> UploadSignatureResponse:
    """Signs a direct-to-Cloudinary upload so the file never transits our
    server (Section 6 free-hosting setup, added post-plan). Scoped to the
    caller's tenant so media from different upazilas don't share a folder."""
    if not (settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="media uploads not configured")

    folder = f"upazila/{actor.tenant_id or 'shared'}"
    timestamp = int(time.time())
    signature = cloudinary.utils.api_sign_request(
        {"timestamp": timestamp, "folder": folder}, settings.CLOUDINARY_API_SECRET
    )
    return UploadSignatureResponse(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        timestamp=timestamp,
        signature=signature,
        folder=folder,
    )
