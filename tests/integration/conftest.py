import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from rag_lab.config import Settings

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


@pytest.fixture(scope="session")
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
