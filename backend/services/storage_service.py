"""
Azure Account Storage Service (Blob Storage)
Handles uploading scanned pictures, fetching saved batch images, and managing storage references.
Includes fallback to local disk storage when Azure credentials are not yet configured.
"""

import os
import uuid
import mimetypes
import logging
from pathlib import Path
from typing import Tuple, Optional
from datetime import datetime, timezone, timedelta

from backend.config import settings

logger = logging.getLogger("document_scan_app.storage")

# Optional Azure Blob import
try:
    from azure.storage.blob import (
        BlobServiceClient,
        BlobClient,
        ContainerClient,
        generate_blob_sas,
        BlobSasPermissions,
        ContentSettings,
    )
    AZURE_STORAGE_AVAILABLE = True
except ImportError:
    AZURE_STORAGE_AVAILABLE = False
    logger.warning("azure-storage-blob package not available.")


class StorageService:
    def __init__(self):
        self.blob_service_client: Optional[BlobServiceClient] = None
        self.container_client: Optional[ContainerClient] = None
        self.is_azure: bool = False
        self.provider_name: str = "Local Storage"
        self._init_client()

    def _init_client(self):
        """Initialize Azure Blob Storage Client or fall back to local disk storage"""
        if settings.is_azure_storage_configured() and AZURE_STORAGE_AVAILABLE:
            try:
                if settings.AZURE_STORAGE_CONNECTION_STRING:
                    self.blob_service_client = BlobServiceClient.from_connection_string(
                        settings.AZURE_STORAGE_CONNECTION_STRING
                    )
                else:
                    account_url = f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
                    self.blob_service_client = BlobServiceClient(
                        account_url=account_url,
                        credential=settings.AZURE_STORAGE_ACCOUNT_KEY
                    )

                # Ensure container exists
                self.container_client = self.blob_service_client.get_container_client(
                    settings.AZURE_STORAGE_CONTAINER_NAME
                )
                try:
                    self.container_client.create_container()
                    logger.info(f"Created Azure Blob container: {settings.AZURE_STORAGE_CONTAINER_NAME}")
                except Exception:
                    # Container might already exist
                    pass

                self.is_azure = True
                self.provider_name = "Azure Blob Storage"
                logger.info("Successfully connected to Azure Account Storage Service.")
                return
            except Exception as e:
                logger.warning(f"Failed to initialize Azure Storage: {e}. Falling back to local storage.")

        # Local storage fallback
        self.is_azure = False
        self.provider_name = "Local Disk Storage (Dev Mode)"
        settings.LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Using local storage at: {settings.LOCAL_STORAGE_DIR}")

    def upload_file(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        person_id: int
    ) -> Tuple[str, str, str]:
        """
        Uploads an image file to Azure Blob Storage (or local storage).
        Returns: (blob_name, storage_reference, container_name)
        """
        # Clean filename and build unique blob name
        clean_name = Path(filename).name.replace(" ", "_")
        unique_prefix = uuid.uuid4().hex[:10]
        blob_name = f"person_{person_id}/{unique_prefix}_{clean_name}"

        if not content_type:
            content_type, _ = mimetypes.guess_type(filename)
            content_type = content_type or "image/jpeg"

        if self.is_azure and self.blob_service_client:
            try:
                blob_client = self.container_client.get_blob_client(blob_name)
                blob_client.upload_blob(
                    file_bytes,
                    overwrite=True,
                    content_settings=ContentSettings(content_type=content_type)
                )
                storage_reference = blob_client.url
                logger.info(f"Uploaded to Azure Blob: {blob_name}")
                return blob_name, storage_reference, settings.AZURE_STORAGE_CONTAINER_NAME
            except Exception as e:
                logger.error(f"Error uploading to Azure Storage: {e}. Falling back to local disk.")

        # Local storage fallback
        local_target = settings.LOCAL_STORAGE_DIR / blob_name
        local_target.parent.mkdir(parents=True, exist_ok=True)
        with open(local_target, "wb") as f:
            f.write(file_bytes)

        storage_reference = f"local://storage_local/{blob_name}"
        return blob_name, storage_reference, "local-storage"

    def get_file_bytes(self, blob_name: str) -> Tuple[bytes, str]:
        """
        Fetches saved image bytes and its mime content type.
        """
        guessed_type, _ = mimetypes.guess_type(blob_name)
        content_type = guessed_type or "image/jpeg"

        if self.is_azure and self.container_client:
            try:
                blob_client = self.container_client.get_blob_client(blob_name)
                downloader = blob_client.download_blob()
                data = downloader.readall()
                properties = blob_client.get_blob_properties()
                if properties.content_settings and properties.content_settings.content_type:
                    content_type = properties.content_settings.content_type
                return data, content_type
            except Exception as e:
                logger.warning(f"Could not fetch from Azure Blob {blob_name}: {e}. Trying local fallback.")

        # Local storage fallback
        local_target = settings.LOCAL_STORAGE_DIR / blob_name
        if local_target.exists():
            with open(local_target, "rb") as f:
                return f.read(), content_type

        raise FileNotFoundError(f"Document file {blob_name} not found in storage.")

    def delete_file(self, blob_name: str) -> bool:
        """Deletes a file from storage"""
        if self.is_azure and self.container_client:
            try:
                blob_client = self.container_client.get_blob_client(blob_name)
                blob_client.delete_blob()
                return True
            except Exception as e:
                logger.warning(f"Failed to delete blob from Azure: {e}")

        local_target = settings.LOCAL_STORAGE_DIR / blob_name
        if local_target.exists():
            try:
                os.remove(local_target)
                return True
            except Exception:
                pass
        return False

    def get_status(self) -> dict:
        return {
            "name": "Azure Storage Account Service",
            "connected": self.is_azure,
            "status_text": "Connected to Azure Blob Storage" if self.is_azure else "Using Local Disk Storage (Dev Fallback)",
            "provider": self.provider_name,
            "details": {
                "container": settings.AZURE_STORAGE_CONTAINER_NAME if self.is_azure else str(settings.LOCAL_STORAGE_DIR),
                "account": settings.mask_secret(settings.AZURE_STORAGE_ACCOUNT_NAME or "Configured via Connection String" if settings.AZURE_STORAGE_CONNECTION_STRING else None)
            }
        }


storage_service = StorageService()
