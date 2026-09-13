from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.dependencies import CurrentUser, get_current_user
from app.core.rate_limit import rate_limit_by_user
from app.modules.uploads import service
from app.modules.uploads.schemas import UploadSignatureResponse

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post(
    "/signature",
    response_model=UploadSignatureResponse,
    dependencies=[Depends(rate_limit_by_user("upload-signature", settings.UPLOAD_SIGNATURES_PER_USER_PER_MINUTE, 60))],
)
def get_upload_signature(actor: CurrentUser = Depends(get_current_user)) -> UploadSignatureResponse:
    """Any authenticated user may request a signature - the actual write
    (e.g. attaching the resulting URL to a listing) still goes through that
    resource's own permission checks."""
    return service.create_upload_signature(actor)
