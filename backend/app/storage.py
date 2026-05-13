"""
File storage abstraction layer.
- Development: Local filesystem
- Production: Azure Blob Storage
"""
import logging
import uuid
from pathlib import Path

from app.config import (
    AZURE_STORAGE_ACCOUNT_URL,
    AZURE_STORAGE_CONNECTION_STRING,
    AZURE_STORAGE_CONTAINER_REFERENCES,
    AZURE_STORAGE_CONTAINER_UPLOADS,
    REFERENCE_PHOTOS_PATH,
    SUBMISSIONS_STORAGE_PATH,
    USE_AZURE_BLOB,
)

logger = logging.getLogger(__name__)

# ─── AZURE BLOB STORAGE CLIENT ─────────────────────────────────────────────────
_blob_service_client = None

def _get_blob_service_client():
    """Lazy-load Azure Blob Service Client."""
    global _blob_service_client
    if _blob_service_client is None and USE_AZURE_BLOB:
        try:
            from azure.storage.blob import BlobServiceClient
            _blob_service_client = BlobServiceClient.from_connection_string(
                AZURE_STORAGE_CONNECTION_STRING
            )
            logger.info("Azure Blob Storage client initialized")
        except ImportError:
            logger.error("azure-storage-blob package not installed. Run: pip install azure-storage-blob")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Azure Blob Storage: {e}")
            raise
    return _blob_service_client


def _ensure_container_exists(container_name: str):
    """Create Azure Blob container if it doesn't exist."""
    client = _get_blob_service_client()
    if client is None:
        return
    try:
        container_client = client.get_container_client(container_name)
        if not container_client.exists():
            container_client.create_container()
            logger.info(f"Created Azure Blob container: {container_name}")
    except Exception as e:
        logger.warning(f"Could not ensure container exists: {e}")


# ─── UNIFIED STORAGE API ───────────────────────────────────────────────────────

def save_upload(
    file_content: bytes,
    submission_id: str,
    image_type: str,
    ext: str = "jpg"
) -> str:
    """
    Save uploaded file. Returns relative path/blob name.

    Args:
        file_content: Raw bytes of the file
        submission_id: Unique submission identifier
        image_type: Type of image (e.g., 'face', 'body', 'front', 'side')
        ext: File extension

    Returns:
        Relative path (local) or blob name (Azure) for storage reference
    """
    name = f"{image_type}_{uuid.uuid4().hex[:12]}.{ext}"
    blob_name = f"{submission_id}/{name}"

    if USE_AZURE_BLOB:
        return _save_to_azure_blob(file_content, blob_name, AZURE_STORAGE_CONTAINER_UPLOADS)
    else:
        return _save_to_local(file_content, blob_name, SUBMISSIONS_STORAGE_PATH)


def save_reference_photo(
    file_content: bytes,
    person_id: str,
    ext: str = "jpg"
) -> str:
    """
    Save reference person photo.

    Args:
        file_content: Raw bytes of the photo
        person_id: Unique person identifier
        ext: File extension

    Returns:
        Relative path (local) or blob name (Azure) for storage reference
    """
    name = f"{person_id}_{uuid.uuid4().hex[:8]}.{ext}"
    blob_name = f"references/{name}"

    if USE_AZURE_BLOB:
        return _save_to_azure_blob(file_content, blob_name, AZURE_STORAGE_CONTAINER_REFERENCES)
    else:
        return _save_to_local(file_content, name, REFERENCE_PHOTOS_PATH)


def get_file_content(relative_path: str, is_reference: bool = False) -> bytes | None:
    """
    Retrieve file content by relative path.

    Args:
        relative_path: The stored path/blob name
        is_reference: Whether this is a reference photo

    Returns:
        File bytes or None if not found
    """
    if USE_AZURE_BLOB:
        container = AZURE_STORAGE_CONTAINER_REFERENCES if is_reference else AZURE_STORAGE_CONTAINER_UPLOADS
        return _get_from_azure_blob(relative_path, container)
    else:
        base_path = REFERENCE_PHOTOS_PATH if is_reference else SUBMISSIONS_STORAGE_PATH
        return _get_from_local(relative_path, base_path)


def delete_file(relative_path: str, is_reference: bool = False) -> bool:
    """
    Delete a file from storage.

    Args:
        relative_path: The stored path/blob name
        is_reference: Whether this is a reference photo

    Returns:
        True if deleted, False otherwise
    """
    if USE_AZURE_BLOB:
        container = AZURE_STORAGE_CONTAINER_REFERENCES if is_reference else AZURE_STORAGE_CONTAINER_UPLOADS
        return _delete_from_azure_blob(relative_path, container)
    else:
        base_path = REFERENCE_PHOTOS_PATH if is_reference else SUBMISSIONS_STORAGE_PATH
        return _delete_from_local(relative_path, base_path)


def get_full_path(relative_path: str) -> Path:
    """Get full local path (for local storage only)."""
    return SUBMISSIONS_STORAGE_PATH / relative_path


def get_url_path(relative_path: str, is_reference: bool = False) -> str:
    """
    Get URL path for serving file.

    For Azure Blob: Returns SAS URL or public URL
    For Local: Returns API path like /api/files/...
    """
    if USE_AZURE_BLOB:
        return _get_azure_blob_url(relative_path, is_reference)
    else:
        prefix = "reference_files" if is_reference else "files"
        return f"/api/{prefix}/{relative_path}"


def file_exists(relative_path: str, is_reference: bool = False) -> bool:
    """Check if a file exists in storage."""
    if USE_AZURE_BLOB:
        container = AZURE_STORAGE_CONTAINER_REFERENCES if is_reference else AZURE_STORAGE_CONTAINER_UPLOADS
        return _azure_blob_exists(relative_path, container)
    else:
        base_path = REFERENCE_PHOTOS_PATH if is_reference else SUBMISSIONS_STORAGE_PATH
        return (base_path / relative_path).exists()


# ─── LOCAL FILE STORAGE IMPLEMENTATION ─────────────────────────────────────────

def _save_to_local(file_content: bytes, relative_path: str, base_path: Path) -> str:
    """Save file to local filesystem."""
    full_path = base_path / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(file_content)
    logger.debug(f"Saved file locally: {full_path}")
    return relative_path


def _get_from_local(relative_path: str, base_path: Path) -> bytes | None:
    """Get file content from local filesystem."""
    full_path = base_path / relative_path
    if full_path.exists():
        return full_path.read_bytes()
    return None


def _delete_from_local(relative_path: str, base_path: Path) -> bool:
    """Delete file from local filesystem."""
    full_path = base_path / relative_path
    if full_path.exists():
        full_path.unlink()
        logger.debug(f"Deleted local file: {full_path}")
        return True
    return False


# ─── AZURE BLOB STORAGE IMPLEMENTATION ─────────────────────────────────────────

def _save_to_azure_blob(file_content: bytes, blob_name: str, container_name: str) -> str:
    """Save file to Azure Blob Storage."""
    _ensure_container_exists(container_name)
    client = _get_blob_service_client()
    blob_client = client.get_blob_client(container=container_name, blob=blob_name)
    blob_client.upload_blob(file_content, overwrite=True)
    logger.debug(f"Saved to Azure Blob: {container_name}/{blob_name}")
    return blob_name


def _get_from_azure_blob(blob_name: str, container_name: str) -> bytes | None:
    """Get file content from Azure Blob Storage."""
    try:
        client = _get_blob_service_client()
        blob_client = client.get_blob_client(container=container_name, blob=blob_name)
        return blob_client.download_blob().readall()
    except Exception as e:
        logger.warning(f"Could not retrieve blob {container_name}/{blob_name}: {e}")
        return None


def _delete_from_azure_blob(blob_name: str, container_name: str) -> bool:
    """Delete file from Azure Blob Storage."""
    try:
        client = _get_blob_service_client()
        blob_client = client.get_blob_client(container=container_name, blob=blob_name)
        blob_client.delete_blob()
        logger.debug(f"Deleted Azure Blob: {container_name}/{blob_name}")
        return True
    except Exception as e:
        logger.warning(f"Could not delete blob {container_name}/{blob_name}: {e}")
        return False


def _azure_blob_exists(blob_name: str, container_name: str) -> bool:
    """Check if blob exists in Azure Blob Storage."""
    try:
        client = _get_blob_service_client()
        blob_client = client.get_blob_client(container=container_name, blob=blob_name)
        return blob_client.exists()
    except Exception:
        return False


def _get_azure_blob_url(blob_name: str, is_reference: bool = False) -> str:
    """
    Get URL for Azure Blob.

    For public containers, returns direct URL.
    For private containers, you would generate a SAS token here.
    """
    container = AZURE_STORAGE_CONTAINER_REFERENCES if is_reference else AZURE_STORAGE_CONTAINER_UPLOADS

    if AZURE_STORAGE_ACCOUNT_URL:
        # Direct URL (assumes public access or SAS in blob_name)
        return f"{AZURE_STORAGE_ACCOUNT_URL.rstrip('/')}/{container}/{blob_name}"
    else:
        # Fallback: proxy through API
        prefix = "references" if is_reference else "files"
        return f"/api/{prefix}/{blob_name}"


def generate_sas_url(blob_name: str, is_reference: bool = False, expiry_hours: int = 1) -> str:
    """
    Generate a SAS URL for temporary access to a blob.

    Args:
        blob_name: The blob name/path
        is_reference: Whether this is a reference photo
        expiry_hours: Hours until the SAS token expires

    Returns:
        SAS URL for the blob
    """
    if not USE_AZURE_BLOB:
        return get_url_path(blob_name, is_reference)

    try:
        from datetime import datetime, timedelta, timezone

        from azure.storage.blob import BlobSasPermissions, generate_blob_sas

        container = AZURE_STORAGE_CONTAINER_REFERENCES if is_reference else AZURE_STORAGE_CONTAINER_UPLOADS
        _get_blob_service_client()

        conn_parts = dict(item.split("=", 1) for item in AZURE_STORAGE_CONNECTION_STRING.split(";") if "=" in item)
        account_name = conn_parts.get("AccountName", "")
        account_key = conn_parts.get("AccountKey", "")

        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=container,
            blob_name=blob_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
        )

        return f"https://{account_name}.blob.core.windows.net/{container}/{blob_name}?{sas_token}"
    except Exception as e:
        logger.error(f"Failed to generate SAS URL: {e}")
        return get_url_path(blob_name, is_reference)
