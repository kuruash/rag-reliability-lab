import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_lab.models import Document, DocumentVersion, VersionStatus


class PublicationError(ValueError):
    """Raised when a version is not eligible for publication."""


def publish_version(session: Session, document_id: uuid.UUID, version: int) -> None:
    """Publish an indexed current version in one transaction."""
    with session.begin():
        document = session.execute(
            select(Document).where(Document.id == document_id).with_for_update()
        ).scalar_one()
        candidate = session.execute(
            select(DocumentVersion)
            .where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.version == version,
            )
            .with_for_update()
        ).scalar_one()

        if document.deleted_at is not None:
            raise PublicationError("cannot publish a deleted document")
        if document.desired_version != version:
            raise PublicationError("version is no longer the latest desired version")
        if candidate.status != VersionStatus.INDEXED:
            raise PublicationError("only an indexed version can be published")
        if document.active_version is not None and version <= document.active_version:
            raise PublicationError("publication must be monotonic")

        if document.active_version is not None:
            previous = session.execute(
                select(DocumentVersion).where(
                    DocumentVersion.document_id == document_id,
                    DocumentVersion.version == document.active_version,
                )
            ).scalar_one()
            previous.status = VersionStatus.SUPERSEDED

        candidate.status = VersionStatus.ACTIVE
        document.active_version = version
