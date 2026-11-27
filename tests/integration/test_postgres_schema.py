import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from rag_lab.config import Settings
from rag_lab.models import Document, DocumentVersion, Tenant, User, VersionStatus
from rag_lab.publication import PublicationError, publish_version

pytestmark = pytest.mark.integration
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _database_identity(database_url: str) -> tuple[str, str, int | None, str | None]:
    parsed_url = make_url(database_url)
    host = parsed_url.host or ""
    if host in {"localhost", "127.0.0.1", "::1"}:
        host = "local"
    return parsed_url.drivername, host, parsed_url.port, parsed_url.database


def _migrate_test_database(database_url: str) -> None:
    migration_environment = os.environ.copy()
    migration_environment["RAG_LAB_DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPOSITORY_ROOT,
        env=migration_environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Alembic migration failed for the integration-test database (exit {result.returncode})"
        )


@pytest.fixture(scope="module")
def database_engine():
    database_url = os.getenv("RAG_LAB_TEST_DATABASE_URL")
    if not database_url:
        pytest.fail("RAG_LAB_TEST_DATABASE_URL must be set for PostgreSQL integration tests")

    development_url = Settings().database_url
    if development_url and _database_identity(database_url) == _database_identity(development_url):
        pytest.fail(
            "RAG_LAB_TEST_DATABASE_URL must target a database different from RAG_LAB_DATABASE_URL"
        )

    _migrate_test_database(database_url)
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        engine.dispose()
        pytest.skip(f"PostgreSQL is not reachable: {exc}")
    yield engine
    engine.dispose()


@pytest.fixture()
def session(database_engine):
    with Session(database_engine) as database_session:
        yield database_session
        database_session.rollback()


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
