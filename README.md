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
PostgreSQL lifecycle schema, and the initial migration.

Prerequisites:

- Python 3.12
- PostgreSQL 15 or newer

Create an environment and install the development dependencies:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Set `RAG_LAB_DATABASE_URL` for the application and Alembic, then apply the
migration:

```bash
export RAG_LAB_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag_lab
.venv/bin/alembic upgrade head
```

Run the liveness test and lint checks:

```bash
.venv/bin/pytest tests/unit
.venv/bin/ruff check .
```

PostgreSQL integration tests require a separate disposable database URL:

```bash
export RAG_LAB_TEST_DATABASE_URL="$RAG_LAB_DATABASE_URL"
.venv/bin/pytest tests/integration
```

Document ingestion, retrieval, vector storage, asynchronous workers, and the
frontend are intentionally not part of this Phase 1 step.

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
