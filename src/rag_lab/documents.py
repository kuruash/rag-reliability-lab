import hashlib
import logging
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final

from botocore.client import BaseClient
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from rag_lab.config import Settings, settings
from rag_lab.models import Document, DocumentVersion, Tenant, User, VersionStatus
from rag_lab.storage_clients import StorageConnectionError, ensure_minio_bucket

logger = logging.getLogger(__name__)

DEV_TENANT_ID: Final = uuid.UUID("00000000-0000-4000-8000-000000000001")
DEV_USER_ID: Final = uuid.UUID("00000000-0000-4000-8000-000000000002")


class UploadValidationError(ValueError):
    """Base class for client-correctable upload errors."""


class UploadTooLargeError(UploadValidationError):
    """Raised when an upload exceeds the configured byte limit."""


class UploadStorageError(ConnectionError):
    """Raised when the original bytes cannot be stored."""


class UploadPersistenceError(RuntimeError):
    """Raised when document metadata cannot be persisted."""


class DocumentNameConflictError(UploadPersistenceError):
    """Raised when the tenant already has a document with the same name."""


@dataclass(frozen=True)
class StoredDocument:
    document_id: uuid.UUID
    version: int
    status: VersionStatus


def document_name_from_filename(filename: str | None) -> str:
    if not filename:
        raise UploadValidationError("a PDF filename is required")
    document_name = PurePosixPath(filename.replace("\\", "/")).name
    if not document_name:
        raise UploadValidationError("a PDF filename is required")
    return document_name


def validate_pdf_upload(
    content: bytes,
    content_type: str | None,
    max_size_bytes: int = settings.max_upload_size_bytes,
) -> None:
    if content_type != "application/pdf":
        raise UploadValidationError("content type must be application/pdf")
    if len(content) > max_size_bytes:
        raise UploadTooLargeError(f"PDF uploads must be {max_size_bytes} bytes or smaller")
    if not content.startswith(b"%PDF-"):
        raise UploadValidationError("file does not have a valid PDF signature")


def _ensure_development_identity(session: Session) -> Tenant:
    tenant = session.get(Tenant, DEV_TENANT_ID)
    if tenant is None:
        tenant = Tenant(id=DEV_TENANT_ID, name="development-tenant")
        session.add(tenant)

    if session.get(User, DEV_USER_ID) is None:
        session.add(
            User(
                id=DEV_USER_ID,
                tenant_id=DEV_TENANT_ID,
                email="development-user@example.invalid",
                role="member",
            )
        )
    return tenant


def _cleanup_object(client: BaseClient, bucket: str, object_key: str) -> None:
    try:
        client.delete_object(Bucket=bucket, Key=object_key)
    except Exception:
        logger.exception(
            "orphaned uploaded object requires reconciliation",
            extra={"bucket": bucket, "object_key": object_key},
        )


def store_document_upload(
    *,
    content: bytes,
    filename: str | None,
    content_type: str | None,
    session: Session,
    object_storage: BaseClient,
    config: Settings = settings,
) -> StoredDocument:
    document_name = document_name_from_filename(filename)
    validate_pdf_upload(content, content_type, config.max_upload_size_bytes)

    document_id = uuid.uuid4()
    version = 1
    object_key = f"documents/{document_id}/versions/{version}/source.pdf"
    checksum = hashlib.sha256(content).hexdigest()
    bucket = config.minio_bucket

    try:
        ensure_minio_bucket(object_storage, bucket)
        object_storage.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=content,
            ContentType="application/pdf",
        )
    except StorageConnectionError as exc:
        raise UploadStorageError("unable to store the PDF in object storage") from exc
    except Exception as exc:
        raise UploadStorageError("unable to store the PDF in object storage") from exc

    try:
        with session.begin():
            tenant = _ensure_development_identity(session)
            document = Document(
                id=document_id,
                tenant_id=tenant.id,
                name=document_name,
                desired_version=version,
                active_version=None,
            )
            document_version = DocumentVersion(
                document_id=document_id,
                version=version,
                object_key=object_key,
                sha256=checksum,
                status=VersionStatus.PENDING,
            )
            session.add_all([document, document_version])
            session.flush()
    except IntegrityError as exc:
        _cleanup_object(object_storage, bucket, object_key)
        raise DocumentNameConflictError(
            "a document with this filename already exists for the development tenant"
        ) from exc
    except SQLAlchemyError as exc:
        _cleanup_object(object_storage, bucket, object_key)
        raise UploadPersistenceError(
            "document metadata could not be persisted; the uploaded object was cleaned up"
        ) from exc

    return StoredDocument(document_id=document_id, version=version, status=VersionStatus.PENDING)
