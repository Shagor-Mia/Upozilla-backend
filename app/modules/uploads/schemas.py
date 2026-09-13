from pydantic import BaseModel


class UploadSignatureResponse(BaseModel):
    """Everything the client needs to POST a file straight to Cloudinary
    (https://api.cloudinary.com/v1_1/{cloud_name}/auto/upload) without the
    file ever passing through our server."""

    cloud_name: str
    api_key: str
    timestamp: int
    signature: str
    folder: str
