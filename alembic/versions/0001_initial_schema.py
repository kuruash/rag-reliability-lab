"""Create the Phase 1 lifecycle schema.

Revision ID: 0001_initial_schema
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    uuid_type = postgresql.UUID(as_uuid=True)
    timestamp = sa.DateTime(timezone=True)

    op.create_table(
        "tenants",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", timestamp, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", timestamp, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name", name="uq_tenants_name"),
    )
    op.create_table(
        "users",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.Column("created_at", timestamp, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", timestamp, nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.CheckConstraint("role IN ('member', 'admin')", name="ck_users_role"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_table(
        "documents",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("desired_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("active_version", sa.Integer, nullable=True),
        sa.Column("deleted_at", timestamp, nullable=True),
        sa.Column("created_at", timestamp, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", timestamp, nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.CheckConstraint("desired_version >= 1", name="ck_documents_desired_version_positive"),
        sa.CheckConstraint(
            "active_version IS NULL OR active_version >= 1",
            name="ck_documents_active_version_positive",
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_documents_tenant_name"),
    )
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])
    op.create_index("ix_documents_tenant_deleted_at", "documents", ["tenant_id", "deleted_at"])
    op.create_table(
        "document_versions",
        sa.Column("document_id", uuid_type, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", timestamp, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", timestamp, nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id", "version"),
        sa.CheckConstraint("version >= 1", name="ck_document_versions_version_positive"),
        sa.CheckConstraint(
            "status IN ("
            "'pending', 'processing', 'retry_pending', 'indexed', "
            "'active', 'superseded', 'failed'"
            ")",
            name="ck_document_versions_status",
        ),
    )
    op.create_index("ix_document_versions_status", "document_versions", ["status"])
    op.create_index(
        "ix_document_versions_document_status", "document_versions", ["document_id", "status"]
    )
    op.create_foreign_key(
        "fk_documents_desired_version",
        "documents",
        "document_versions",
        ["id", "desired_version"],
        ["document_id", "version"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_documents_active_version",
        "documents",
        "document_versions",
        ["id", "active_version"],
        ["document_id", "version"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.execute(
        """
        CREATE FUNCTION prevent_version_source_metadata_update()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.object_key IS DISTINCT FROM OLD.object_key
               OR NEW.sha256 IS DISTINCT FROM OLD.sha256 THEN
                RAISE EXCEPTION 'document version source metadata is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER document_version_source_metadata_immutable
        BEFORE UPDATE ON document_versions
        FOR EACH ROW EXECUTE FUNCTION prevent_version_source_metadata_update()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS document_version_source_metadata_immutable ON document_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_version_source_metadata_update()")
    op.drop_constraint("fk_documents_active_version", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_desired_version", "documents", type_="foreignkey")
    op.drop_index("ix_document_versions_document_status", table_name="document_versions")
    op.drop_index("ix_document_versions_status", table_name="document_versions")
    op.drop_table("document_versions")
    op.drop_index("ix_documents_tenant_deleted_at", table_name="documents")
    op.drop_index("ix_documents_tenant_id", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_table("users")
    op.drop_table("tenants")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
