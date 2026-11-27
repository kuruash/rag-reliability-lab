SHELL := /bin/bash

PYTHON ?= python3.12
VENV ?= .venv
PYTHON_BIN := $(VENV)/bin/python
COMPOSE ?= docker compose

-include .env

RAG_LAB_POSTGRES_DB ?= rag_lab
RAG_LAB_POSTGRES_USER ?= rag_lab
RAG_LAB_POSTGRES_PASSWORD ?= rag_lab_dev
RAG_LAB_POSTGRES_HOST_PORT ?= 55433
RAG_LAB_DATABASE_URL ?= postgresql+psycopg://rag_lab:rag_lab_dev@localhost:55433/rag_lab
RAG_LAB_TEST_DATABASE_URL ?= postgresql+psycopg://rag_lab:rag_lab_dev@localhost:55433/rag_lab_test
RAG_LAB_QDRANT_HTTP_PORT ?= 6333
RAG_LAB_QDRANT_GRPC_PORT ?= 6334
RAG_LAB_QDRANT_URL ?= http://localhost:6333
RAG_LAB_MINIO_ROOT_USER ?= rag_lab_minio
RAG_LAB_MINIO_ROOT_PASSWORD ?= rag_lab_minio_dev
RAG_LAB_MINIO_API_PORT ?= 9000
RAG_LAB_MINIO_CONSOLE_PORT ?= 9001
RAG_LAB_MINIO_ENDPOINT ?= http://localhost:9000

export RAG_LAB_POSTGRES_DB RAG_LAB_POSTGRES_USER RAG_LAB_POSTGRES_PASSWORD
export RAG_LAB_POSTGRES_HOST_PORT RAG_LAB_DATABASE_URL RAG_LAB_TEST_DATABASE_URL
export RAG_LAB_QDRANT_HTTP_PORT RAG_LAB_QDRANT_GRPC_PORT RAG_LAB_QDRANT_URL
export RAG_LAB_MINIO_ROOT_USER RAG_LAB_MINIO_ROOT_PASSWORD
export RAG_LAB_MINIO_API_PORT RAG_LAB_MINIO_CONSOLE_PORT RAG_LAB_MINIO_ENDPOINT

.PHONY: setup dev test lint format-check

setup:
	@test -x "$(PYTHON_BIN)" || $(PYTHON) -m venv "$(VENV)"
	@$(PYTHON_BIN) -m pip install -e '.[dev]'
	@test -f .env || cp .env.example .env
	@$(COMPOSE) up -d --wait
	@if ! $(COMPOSE) exec -T postgres psql -U "$${RAG_LAB_POSTGRES_USER}" -d "$${RAG_LAB_POSTGRES_DB}" -Atqc "SELECT 1 FROM pg_database WHERE datname = 'rag_lab_test'" | grep -qx 1; then \
		$(COMPOSE) exec -T postgres createdb -U "$${RAG_LAB_POSTGRES_USER}" rag_lab_test; \
	fi
	@$(PYTHON_BIN) -m alembic upgrade head
	@RAG_LAB_DATABASE_URL="$(RAG_LAB_TEST_DATABASE_URL)" $(PYTHON_BIN) -m alembic upgrade head

dev:
	@$(COMPOSE) up -d --wait
	@$(PYTHON_BIN) -m uvicorn rag_lab.main:app --reload

test:
	@$(PYTHON_BIN) -m pytest -q --junitxml=/tmp/rag-lab-pytest.xml
	@$(PYTHON_BIN) -c 'import sys, xml.etree.ElementTree as ET; root = ET.parse("/tmp/rag-lab-pytest.xml").getroot(); skipped = sum(int(s.attrib.get("skipped", 0)) for s in root.iter("testsuite")); sys.exit(f"{skipped} test(s) were skipped") if skipped else sys.exit(0)'

lint:
	@$(PYTHON_BIN) -m ruff check .

format-check:
	@$(PYTHON_BIN) -m ruff format --check .

