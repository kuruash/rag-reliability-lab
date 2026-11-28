import uuid

import pytest
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from rag_lab.models import Document, DocumentVersion, Tenant, User, VersionStatus
from rag_lab.publication import PublicationError, publish_version

pytestmark = pytest.mark.integration


def make_document(session: Session, *, name: str = "policy") -> tuple[Document, DocumentVersion]:
    tenant = Tenant(name=f"tenant-{uuid.uuid4()}")
    document = Document(tenant=tenant, name=name, desired_version=1)
    version = DocumentVersion(
        document=document,
        version=1,
        object_key=f"documents/{uuid.uuid4()}",
        sha256="a" * 64,
        status=VersionStatus.INDEXED,
    )
    session.add(document)
    session.flush()
    return document, version


def test_schema_enforces_composite_version_reference(session: Session) -> None:
    tenant = Tenant(name=f"tenant-{uuid.uuid4()}")
    document = Document(tenant=tenant, name="missing-version", desired_version=1)
    session.add(document)

    with pytest.raises(IntegrityError):
        session.commit()


def test_schema_enforces_tenant_scoped_user_email_uniqueness(session: Session) -> None:
    tenant = Tenant(name=f"tenant-{uuid.uuid4()}")
    session.add_all(
        [
            User(tenant=tenant, email="owner@example.com"),
            User(tenant=tenant, email="owner@example.com"),
        ]
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_source_metadata_is_immutable(session: Session) -> None:
    _, version = make_document(session)
    version.status = VersionStatus.PROCESSING
    session.flush()
    assert version.status == VersionStatus.PROCESSING

    version_key = (version.document_id, version.version)
    original_object_key = version.object_key
    original_sha256 = version.sha256
    session.commit()

    persisted_version = session.get(DocumentVersion, version_key)
    assert persisted_version is not None
    persisted_version.object_key = "documents/changed"
    with pytest.raises(ProgrammingError, match="source metadata is immutable"):
        session.flush()

    session.rollback()
    persisted_version = session.get(DocumentVersion, version_key)
    assert persisted_version is not None
    assert persisted_version.object_key == original_object_key
    assert persisted_version.sha256 == original_sha256
    persisted_version.sha256 = "b" * 64

    with pytest.raises(ProgrammingError, match="source metadata is immutable"):
        session.flush()

    session.rollback()
    persisted_version = session.get(DocumentVersion, version_key)
    assert persisted_version is not None
    assert persisted_version.object_key == original_object_key
    assert persisted_version.sha256 == original_sha256


def test_publication_is_monotonic_and_rejects_deleted_documents(session: Session) -> None:
    document, version = make_document(session)
    document_id = document.id
    version_number = version.version
    session.commit()

    publish_version(session, document_id, version_number)
    session.refresh(document)
    assert document.active_version == 1

    document.deleted_at = version.created_at
    session.commit()

    with pytest.raises(PublicationError, match="deleted"):
        publish_version(session, document_id, version_number)
