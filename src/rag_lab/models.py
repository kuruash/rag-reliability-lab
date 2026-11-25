import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class VersionStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    RETRY_PENDING = "retry_pending"
    INDEXED = "indexed"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    users: Mapped[list["User"]] = relationship(back_populates="tenant")
    documents: Mapped[list["Document"]] = relationship(back_populates="tenant")


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        CheckConstraint("role IN ('member', 'admin')", name="ck_users_role"),
        Index("ix_users_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")

    tenant: Mapped[Tenant] = relationship(back_populates="users")


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["id", "desired_version"],
            ["document_versions.document_id", "document_versions.version"],
            name="fk_documents_desired_version",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["id", "active_version"],
            ["document_versions.document_id", "document_versions.version"],
            name="fk_documents_active_version",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("desired_version >= 1", name="ck_documents_desired_version_positive"),
        CheckConstraint(
            "active_version IS NULL OR active_version >= 1",
            name="ck_documents_active_version_positive",
        ),
        UniqueConstraint("tenant_id", "name", name="uq_documents_tenant_name"),
        Index("ix_documents_tenant_id", "tenant_id"),
        Index("ix_documents_tenant_deleted_at", "tenant_id", "deleted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    desired_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped[Tenant] = relationship(back_populates="documents")
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys=lambda: [DocumentVersion.document_id],
    )


class DocumentVersion(TimestampMixin, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        CheckConstraint("version >= 1", name="ck_document_versions_version_positive"),
        CheckConstraint(
            "status IN ("
            "'pending', 'processing', 'retry_pending', 'indexed', "
            "'active', 'superseded', 'failed'"
            ")",
            name="ck_document_versions_status",
        ),
        Index("ix_document_versions_status", "status"),
        Index("ix_document_versions_document_status", "document_id", "status"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[VersionStatus] = mapped_column(
        String(32), nullable=False, default=VersionStatus.PENDING
    )

    document: Mapped[Document] = relationship(back_populates="versions", foreign_keys=[document_id])
