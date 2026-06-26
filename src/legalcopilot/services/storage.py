"""Storage service — S3 with local filesystem fallback for dev mode.

STORAGE_BACKEND settings:
  - "s3": Force S3 (fails if no credentials)
  - "local": Force local filesystem
  - "auto": S3 if AWS_ACCESS_KEY_ID is set, else local
"""

import logging
import os
import re
import uuid

from legalcopilot.config import settings

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 52_428_800  # 50 MB

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
}

EXTENSION_TO_CONTENT_TYPE = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
}


class StorageError(Exception):
    pass


class StorageConfigError(StorageError):
    pass


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to safe chars only."""
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
    name = re.sub(r"_+", "_", name)
    return name[:200]


def _validate_id(value: str, label: str) -> None:
    """Validate that an ID contains only safe characters."""
    if not value or not re.match(r"^[a-zA-Z0-9_-]+$", value):
        raise StorageError(f"Invalid {label}: must be non-empty alphanumeric")


def _make_key(firm_id: str, case_id: str, filename: str) -> str:
    """Build storage key: {firm_id}/{case_id}/{uuid}_{filename}."""
    _validate_id(firm_id, "firm_id")
    _validate_id(case_id, "case_id")
    safe_name = _sanitize_filename(filename)
    return f"{firm_id}/{case_id}/{uuid.uuid4()}_{safe_name}"


def use_s3() -> bool:
    """Determine whether to use S3 based on STORAGE_BACKEND setting."""
    backend = settings.STORAGE_BACKEND.lower()
    if backend == "s3":
        return True
    if backend == "local":
        return False
    # auto: use S3 if credentials present
    return bool(settings.AWS_ACCESS_KEY_ID)


def _get_s3_client():
    """Create a boto3 S3 client."""
    import boto3

    return boto3.client(
        "s3",
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def _local_path(key: str) -> str:
    """Resolve a storage key to a local filesystem path with containment check."""
    base = os.path.realpath(settings.LOCAL_STORAGE_DIR)
    resolved = os.path.realpath(os.path.join(base, key))
    if not resolved.startswith(base + os.sep) and resolved != base:
        raise StorageError("Invalid storage key: path traversal detected")
    return resolved


def generate_presigned_upload_url(
    case_id: str, filename: str, firm_id: str, content_type: str
) -> dict:
    """Generate a presigned upload URL (S3) or local upload info."""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise StorageError(f"Content type not allowed: {content_type}")

    key = _make_key(firm_id, case_id, filename)

    if use_s3():
        client = _get_s3_client()
        presigned = client.generate_presigned_post(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 0, MAX_UPLOAD_SIZE],
            ],
            ExpiresIn=settings.S3_UPLOAD_EXPIRY,
        )
        return {
            "upload_url": presigned["url"],
            "fields": presigned["fields"],
            "key": key,
            "expires_in": settings.S3_UPLOAD_EXPIRY,
            "backend": "s3",
        }

    # Local fallback
    return {
        "upload_url": "local://upload",
        "fields": {},
        "key": key,
        "expires_in": settings.S3_UPLOAD_EXPIRY,
        "backend": "local",
    }


def generate_presigned_download_url(storage_url: str, expires_in: int = 0) -> str:
    """Generate a presigned download URL for the file."""
    if not expires_in:
        expires_in = settings.S3_PRESIGN_EXPIRY

    key = _parse_key(storage_url)

    if use_s3():
        client = _get_s3_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": key},
            ExpiresIn=expires_in,
        )

    # Local: return a path reference
    return f"local://{key}"


def upload_file(
    file_bytes: bytes,
    case_id: str,
    filename: str,
    firm_id: str,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload file bytes and return the storage URL."""
    key = _make_key(firm_id, case_id, filename)

    if use_s3():
        import io

        client = _get_s3_client()
        client.upload_fileobj(
            io.BytesIO(file_bytes),
            settings.S3_BUCKET,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        return f"s3://{settings.S3_BUCKET}/{key}"

    # Local — enforce size limit
    if len(file_bytes) > MAX_UPLOAD_SIZE:
        raise StorageError(f"File exceeds maximum size ({MAX_UPLOAD_SIZE} bytes)")
    path = _local_path(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(file_bytes)
    return f"local://{key}"


def download_file(storage_url: str) -> bytes:
    """Download file bytes from storage.

    Enforces MAX_UPLOAD_SIZE to prevent unbounded memory consumption.
    """
    key = _parse_key(storage_url)

    if storage_url.startswith("local://"):
        path = _local_path(key)
        if not os.path.exists(path):
            raise StorageError(f"File not found: {key}")
        file_size = os.path.getsize(path)
        if file_size > MAX_UPLOAD_SIZE:
            raise StorageError(f"File exceeds maximum size ({MAX_UPLOAD_SIZE} bytes)")
        with open(path, "rb") as f:
            return f.read()

    if use_s3():
        import io

        client = _get_s3_client()
        # Check file size before downloading
        try:
            head = client.head_object(Bucket=settings.S3_BUCKET, Key=key)
            if head.get("ContentLength", 0) > MAX_UPLOAD_SIZE:
                raise StorageError(f"File exceeds maximum size ({MAX_UPLOAD_SIZE} bytes)")
        except client.exceptions.NoSuchKey:
            raise StorageError(f"File not found: {key}")
        buf = io.BytesIO()
        client.download_fileobj(settings.S3_BUCKET, key, buf)
        buf.seek(0)
        return buf.read()

    raise StorageError(f"Cannot download: {storage_url}")


def delete_file(storage_url: str) -> bool:
    """Delete a file from storage."""
    try:
        key = _parse_key(storage_url)
        if storage_url.startswith("local://"):
            path = _local_path(key)
            if os.path.exists(path):
                os.remove(path)
            return True
        if use_s3():
            client = _get_s3_client()
            client.delete_object(Bucket=settings.S3_BUCKET, Key=key)
            return True
        return False
    except Exception:
        logger.exception("Failed to delete file: %s", storage_url)
        return False


def _parse_key(storage_url: str) -> str:
    """Extract the storage key from a storage URL."""
    if storage_url.startswith("s3://"):
        # s3://bucket/key -> key
        parts = storage_url[5:].split("/", 1)
        return parts[1] if len(parts) > 1 else parts[0]
    if storage_url.startswith("local://"):
        return storage_url[8:]
    raise StorageError(f"Unrecognized storage URL scheme: {storage_url[:20]}")
