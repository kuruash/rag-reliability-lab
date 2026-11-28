# RAG Reliability Lab

A reproducible testbed for investigating reliability failures, document lifecycle consistency, and recovery strategies in Retrieval-Augmented Generation (RAG) systems.

> **Project status:** Early development — architecture defined, implementation in progress.

## Overview

RAG Reliability Lab is a document-based RAG application with a reliability testing framework built around it.

Users will be able to upload documents, update them, search their contents, and ask questions with answers grounded in source evidence.

Beyond basic RAG functionality, the project focuses on what happens when things go wrong:

- What happens if a worker crashes halfway through indexing?
- Can an older document version accidentally replace a newer one?
- What happens when the same indexing job runs multiple times?
- Can deleted or outdated content still appear in search results?
- What happens if a database update succeeds but queue publishing fails?

The goal is to build a functioning RAG system, introduce controlled failures, and evaluate whether the architecture preserves its correctness guarantees.

## Architecture

The system follows a modular monolith architecture with separate API and background worker processes.

| Component | Technology | Responsibility |
|---|---|---|
| API | Python, FastAPI | Document management, search, and chat |
| Database | PostgreSQL | Authoritative document and version state |
| Vector database | Qdrant | Embeddings and similarity search |
| Object storage | MinIO / S3 | Original document versions |
| Messaging | Redis Streams | Asynchronous indexing jobs |
| Workers | Python | Parsing, chunking, embedding, and indexing |
| Embeddings | Sentence Transformers | Reproducible local embeddings |
| LLM | Provider adapter | Evidence-grounded answer generation |
| Frontend | React, TypeScript | Document management and chat |
| Testing | pytest | Automated correctness and reliability tests |
| Observability | OpenTelemetry | Tracing and metrics |
| Infrastructure | Docker Compose | Local development environment |

PostgreSQL acts as the source of truth for document lifecycle state. Qdrant provides vector search, but retrieved evidence must be validated against authoritative document state before being exposed to users.

See [System Architecture](docs/architecture.md) for the complete design.

## Planned Features

### Document management

- Upload and store original documents.
- Create new document versions.
- Track ingestion progress.
- View document version history.
- Delete documents with logical revocation and asynchronous cleanup.

### Retrieval and answer generation

- Semantic search using vector embeddings.
- Tenant-scoped retrieval.
- Validation of current document versions.
- Grounded LLM answers with source citations.
- Insufficient-evidence responses when appropriate.

### Reliability engineering

- Asynchronous ingestion with Redis Streams.
- Transactional outbox for durable job dispatch.
- Idempotent document indexing.
- Atomic document version publication.
- Worker retry and crash recovery.
- Protection against stale and unauthorized evidence.

### Reliability experiments

- Deterministic fault injection.
- Controlled worker execution ordering.
- Automated invariant verification.
- Baseline versus faulty-variant comparisons.
- Reproducible experiment reports.

These capabilities are planned and will be implemented incrementally.

## Reliability Invariants

The project aims to enforce seven initial guarantees:

| ID | Guarantee |
|---|---|
| INV-01 | Older versions cannot replace newer published versions. |
| INV-02 | Superseded chunks cannot appear through normal retrieval after replacement. |
| INV-03 | Reprocessing cannot create duplicate logical chunks. |
| INV-04 | Partially indexed versions cannot become active. |
| INV-05 | Effective deletion prevents subsequent retrieval. |
| INV-06 | Tenant data remains isolated. |
| INV-07 | Failed ingestion jobs remain observable and recoverable or explicitly terminal. |

See [Reliability Invariants](docs/invariants.md) for definitions and planned verification methods.

## Planned Failure Experiments

| ID | Scenario | What it tests |
|---|---|---|
| F-001 | Skip obsolete-chunk cleanup | Physical storage versus stale evidence visibility |
| F-002 | Repeated job delivery | Idempotency |
| F-003 | Out-of-order indexing completion | Version publication correctness |
| F-004 | Worker crash during indexing | Partial-write recovery |
| F-005 | Deletion during in-flight queries | Deletion visibility and read consistency |
| F-006 | Queue publishing failure after database commit | Transactional outbox recovery |

Faults will be deliberately injected in isolated environments. Experiment reports will clearly distinguish induced failures from independently observed defects.

## Development Roadmap

- [ ] **Phase 1 — Foundation:** Python project, Docker infrastructure, PostgreSQL schema, migrations, and initial tests.
- [ ] **Phase 2 — Core RAG:** Document ingestion, indexing, retrieval, grounded answers, and version updates.
- [ ] **Phase 3 — Reliability:** Background workers, Redis Streams, transactional outbox, retries, and atomic publication.
- [ ] **Phase 4 — Security:** Tenant authorization, retrieval validation, deletion guarantees, and API hardening.
- [ ] **Phase 5 — Experiments:** Deterministic fault injection, invariant testing, and reproducible reports.
- [ ] **Phase 6 — Public Release:** Frontend, observability, CI/CD, documentation, and developer setup.

The first implementation milestone is:

**Create → Index → Search → Update → Search**

This will establish a functioning document RAG application before introducing asynchronous reliability experiments.

## Getting Started

Phase 1 currently provides the Python package, the liveness endpoint, the
PostgreSQL lifecycle schema, the initial migration, and local PostgreSQL,
Qdrant, and MinIO-compatible infrastructure.

Prerequisites:

- Python 3.12
- Docker Desktop or Docker Engine with Compose

The reproducible setup command creates a Python 3.12 virtual environment,
installs development dependencies, starts Compose, provisions the separate
integration-test database, and applies migrations to both databases:

```bash
make setup
```

To customize local credentials or ports, copy `.env.example` to `.env` and
edit it before running `make setup`. The example contains development-only
defaults and no production credentials.

The local infrastructure contains these services:

| Service | Purpose | Host ports |
|---|---|---|
| PostgreSQL 17 | Authoritative document lifecycle state | `127.0.0.1:55433` |
| Qdrant | Derived vector index | `127.0.0.1:6333` HTTP, `127.0.0.1:6334` gRPC |
| MinIO-compatible object storage | Original document versions | `127.0.0.1:9000` API, `127.0.0.1:9001` console |

The Compose file binds services to localhost only. PostgreSQL uses host port
`55433` so it does not conflict with an existing PostgreSQL server on `5432`.

Start only the infrastructure:

```bash
docker compose up -d
docker compose ps
```

Check service logs or health status:

```bash
docker compose logs -f postgres
docker inspect --format '{{.Name}} {{.State.Health.Status}}' \
  $(docker compose ps -q postgres) \
  $(docker compose ps -q qdrant) \
  $(docker compose ps -q minio)
```

The named volumes `rag_lab_postgres_data`, `rag_lab_qdrant_data`, and
`rag_lab_minio_data` preserve data across `docker compose stop`, `docker
compose down`, and container restarts. Do not use `docker compose down -v`
unless you intentionally want to remove these local data volumes.

The example environment configures `RAG_LAB_DATABASE_URL` for `rag_lab` and
`RAG_LAB_TEST_DATABASE_URL` for `rag_lab_test`. Integration tests verify that
these URLs target different databases and apply the Alembic migrations to the
test database before running schema checks. `make setup` creates
`rag_lab_test` only when it does not already exist.

The FastAPI application and Alembic use `RAG_LAB_DATABASE_URL` from `.env`:
`postgresql+psycopg://rag_lab:rag_lab_dev@localhost:55433/rag_lab`. From a
future container on the Compose network, the equivalent PostgreSQL URL would
use `postgres:5432` instead of `localhost:55433`.

Qdrant and MinIO connectivity settings are also supplied through `.env`.
Qdrant uses `RAG_LAB_QDRANT_URL` and an optional API key. MinIO uses
`RAG_LAB_MINIO_ENDPOINT`, `RAG_LAB_MINIO_ROOT_USER`, and
`RAG_LAB_MINIO_ROOT_PASSWORD` for this local development environment.

Run the complete test suite, including PostgreSQL, Qdrant, and MinIO integration
tests:

```bash
make test
```

`make test` fails if any test is skipped. Run the quality checks directly with:

```bash
make lint
make format-check
```

Run the FastAPI development server with Compose services available:

```bash
make dev
```

The external-storage integration tests list Qdrant collections and create a
unique temporary MinIO bucket. They upload, read, and delete one object, then
remove the bucket, so they do not use development buckets or collections.

The Phase 2 storage-only upload endpoint accepts a PDF as multipart form data:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/documents \
  -F 'file=@example.pdf;type=application/pdf'
```

It returns `201 Created` with `document_id`, `version`, and `status: "pending"`.
The original bytes are stored in the configured MinIO bucket and the matching
PostgreSQL document/version rows are created with `active_version` unset. This
step does not start ingestion and does not return a job ID; asynchronous
processing is deferred to Phase 3. The development endpoint uses the seeded
local tenant identity and ignores client-supplied tenant IDs.

Phase 2 Step 2 provides pure PDF parsing and text chunking helpers for the
future ingestion worker. Parsing uses `pypdf` and returns one immutable record
per page with a one-based page number. Chunking normalizes whitespace and uses
Unicode character counts, not tokens or bytes. `RAG_LAB_CHUNK_SIZE` defaults to
1000 characters and `RAG_LAB_CHUNK_OVERLAP` defaults to 100 characters; overlap
must be non-negative and smaller than the chunk size. Chunks retain document
ID, version, page number, and a deterministic zero-based document chunk index.

Malformed, empty, encrypted, and image-only PDFs are rejected explicitly.
Image-only PDFs are not OCR'd in this milestone, and pages with no text inside
an otherwise text-bearing PDF produce no chunks. Parsing and chunking do not
change document status or publish versions.

Stop services while retaining their data:

```bash
docker compose stop
```

Stop and remove the containers and network while retaining named volumes:

```bash
docker compose down
```

Document ingestion, retrieval, asynchronous workers, Redis, and the frontend
are intentionally not part of this Phase 1 step.

GitHub Actions runs the same setup, lint, formatting, and test commands on
pull requests and pushes to `main`. CI uses disposable development credentials
and fresh service containers; it does not use local Docker volumes.

## Documentation

- [System Architecture](docs/architecture.md) — Components, data flows, database schema, and APIs.
- [Reliability Invariants](docs/invariants.md) — Correctness guarantees and testing requirements.
- [Design Decisions](docs/design-decisions.md) — Architectural decisions, tradeoffs, and deferred features.

## Project Philosophy

A RAG system should do more than retrieve relevant text and generate plausible answers. It should behave predictably when documents change, workers fail, jobs repeat, or requests arrive concurrently.

This project treats reliability as a measurable engineering property.

The objective is not to claim that any particular vector database or framework is defective. It is to understand failure modes, reproduce them under controlled conditions, and evaluate the effectiveness of different recovery strategies.

## Contributing

The project is in early development. Contribution guidelines and development workflows will be added as the implementation matures.

Issues and technical feedback are welcome.

## License

Licensed under the [Apache License 2.0](LICENSE).
