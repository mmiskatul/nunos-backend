import hashlib
import time
from pathlib import Path
from typing import Literal

import httpx
from fastapi import HTTPException, UploadFile, status

from app.core.config import Settings

# Cloudinary resource types supported by this uploader
ResourceType = Literal["image", "auto"]


class CloudinaryUploader:
    def __init__(self, settings: Settings):
        self.settings = settings

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    async def upload_image(self, file: UploadFile, *, folder_suffix: str = "images") -> str:
        """Upload an image file to Cloudinary and return its secure_url.

        Uses the ``image`` resource type so Cloudinary performs image-specific
        optimisation / validation on ingest.
        """
        return await self._upload(file, resource_type="image", folder_suffix=folder_suffix)

    async def upload_vendor_document(self, file: UploadFile, *, folder_suffix: str = "vendor-documents") -> str:
        """Upload any file (PDF, image, …) using the ``auto`` resource type.

        Kept for backward-compatibility with KYC/document uploads that may be
        non-image formats (e.g. PDF trade-licence scans).
        """
        return await self._upload(file, resource_type="auto", folder_suffix=folder_suffix)

    # ------------------------------------------------------------------
    # Internal implementation
    # ------------------------------------------------------------------

    async def _upload(self, file: UploadFile, *, resource_type: ResourceType, folder_suffix: str) -> str:
        """Sign and POST a file to the Cloudinary Upload API.

        Returns the ``secure_url`` string on success, raises ``HTTPException``
        on configuration errors or Cloudinary API failures.
        """
        cloud_name = self.settings.cloudinary_cloud_name
        api_key = self.settings.cloudinary_api_key
        api_secret = self.settings.cloudinary_api_secret

        if not cloud_name or not api_key or not api_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cloudinary is not configured on the backend.",
            )

        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

        timestamp = int(time.time())
        folder = f"{self.settings.cloudinary_folder}/{folder_suffix}"
        public_id = f"{timestamp}-{Path(file.filename or 'upload').stem}"

        # SHA-1 signature required by Cloudinary signed uploads
        signature_base = f"folder={folder}&public_id={public_id}&timestamp={timestamp}{api_secret}"
        signature = hashlib.sha1(signature_base.encode("utf-8")).hexdigest()

        multipart_files = {
            "file": (file.filename or "upload", file_bytes, file.content_type or "application/octet-stream")
        }
        form_data = {
            "api_key": api_key,
            "timestamp": str(timestamp),
            "folder": folder,
            "public_id": public_id,
            "signature": signature,
        }

        upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/{resource_type}/upload"

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(upload_url, data=form_data, files=multipart_files)

        payload = response.json()
        secure_url = payload.get("secure_url")

        if response.is_error or not secure_url:
            detail = payload.get("error", {}).get("message") or "Cloudinary upload failed."
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)

        return secure_url
