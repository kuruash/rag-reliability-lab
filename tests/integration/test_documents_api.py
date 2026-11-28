import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_lab import main as main_module
from rag_lab.config import settings
from rag_lab.db import get_session
from rag_lab.documents import DEV_TENANT_ID
from rag_lab.models import Document, DocumentVersion, Tenant, User, VersionStatus
from rag_lab.storage_clients import create_minio_client

pytestmark = pytest.mark.integration


@pytest.fixture()
def upload_client(database_engine, monkeypatch):
    bucket = f"rag-lab-upload-it-{uuid.uuid4().hex}"
    monkeypatch.setattr(settings, "minio_bucket", bucket)

    def override_get_session():
        with Session(database_engine) as request_session:
            yield request_session

    main_module.app.dependency_overrides[get_session] = override_get_session
    with TestClient(main_module.app) as client:
        yield client, bucket
    main_module.app.dependency_overrides.clear()

    object_storage = create_minio_client()
    try:
        objects = object_storage.list_objects_v2(Bucket=bucket).get("Contents", [])
        for item in objects:
            object_storage.delete_object(Bucket=bucket, Key=item["Key"])
        object_storage.delete_bucket(Bucket=bucket)
    except Exception:
        pass
    finally:
        object_storage.close()


def pdf_bytes() -> bytes:
    return b"%PDF-1.7\nminimal test document\n%%EOF\n"


def test_upload_creates_pending_version_and_stores_source(upload_client, session: Session) -> None:
    client, bucket = upload_client
    content = pdf_bytes()
    filename = f"policy-{uuid.uuid4()}.pdf"

    response = client.post(
        "/api/v1/documents",
        files={"file": (filename, content, "application/pdf")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["version"] == 1
    assert payload["status"] == "pending"

    document_id = uuid.UUID(payload["document_id"])
    document = session.get(Document, document_id)
    assert document is not None
    assert document.tenant_id == DEV_TENANT_ID
    assert document.name == filename
    assert document.desired_version == 1
    assert document.active_version is None

    version = session.get(DocumentVersion, (document_id, 1))
    assert version is not None
    assert version.status == VersionStatus.PENDING
    assert version.object_key == f"documents/{document_id}/versions/1/source.pdf"
    assert version.sha256 == hashlib.sha256(content).hexdigest()
    assert session.scalar(select(Tenant).where(Tenant.id == DEV_TENANT_ID)) is not None
    assert session.scalar(select(User).where(User.tenant_id == DEV_TENANT_ID)) is not None

    object_storage = create_minio_client()
    try:
        stored = object_storage.get_object(Bucket=bucket, Key=version.object_key)
        assert stored["Body"].read() == content
    finally:
        object_storage.close()


@pytest.mark.parametrize(
    ("content", "content_type", "expected_status"),
    [(b"%PDF-1.7", "text/plain", 400), (b"not a PDF", "application/pdf", 400)],
)
def test_upload_rejects_invalid_files(
    upload_client, content, content_type, expected_status
) -> None:
    client, _ = upload_client
    response = client.post(
        "/api/v1/documents",
        files={"file": (f"invalid-{uuid.uuid4()}.pdf", content, content_type)},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"]


def test_upload_rejects_files_over_configured_limit(upload_client, monkeypatch) -> None:
    client, _ = upload_client
    monkeypatch.setattr(settings, "max_upload_size_bytes", 10)

    response = client.post(
        "/api/v1/documents",
        files={"file": ("large.pdf", b"%PDF-1.7\nmore bytes", "application/pdf")},
    )

    assert response.status_code == 413


def test_upload_uses_trusted_development_tenant(upload_client, session: Session) -> None:
    client, _ = upload_client
    supplied_tenant_id = uuid.uuid4()
    filename = f"tenant-{uuid.uuid4()}.pdf"

    response = client.post(
        "/api/v1/documents",
        data={"tenant_id": str(supplied_tenant_id)},
        files={"file": (filename, pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 201
    document = session.get(Document, uuid.UUID(response.json()["document_id"]))
    assert document is not None
    assert document.tenant_id == DEV_TENANT_ID
    assert document.tenant_id != supplied_tenant_id


def test_duplicate_database_write_cleans_up_uploaded_object(upload_client) -> None:
    client, bucket = upload_client
    filename = f"duplicate-{uuid.uuid4()}.pdf"
    first = client.post(
        "/api/v1/documents",
        files={"file": (filename, pdf_bytes(), "application/pdf")},
    )
    assert first.status_code == 201

    object_storage = create_minio_client()
    try:
        before = object_storage.list_objects_v2(Bucket=bucket).get("Contents", [])
        first_keys = {item["Key"] for item in before}
    finally:
        object_storage.close()

    second = client.post(
        "/api/v1/documents",
        files={"file": (filename, b"%PDF-1.7\nreplacement\n%%EOF", "application/pdf")},
    )
    assert second.status_code == 409

    object_storage = create_minio_client()
    try:
        after = object_storage.list_objects_v2(Bucket=bucket).get("Contents", [])
        assert {item["Key"] for item in after} == first_keys
    finally:
        object_storage.close()


def test_storage_failure_returns_clear_error(upload_client, monkeypatch) -> None:
    client, _ = upload_client

    class BrokenStorage:
        def head_bucket(self, **kwargs):
            raise RuntimeError("connection refused")

        def close(self):
            return None

    monkeypatch.setattr(main_module, "create_minio_client", lambda: BrokenStorage())
    response = client.post(
        "/api/v1/documents",
        files={"file": ("unavailable.pdf", pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "unable to store the PDF in object storage"
