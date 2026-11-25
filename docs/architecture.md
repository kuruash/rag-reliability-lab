# RAG Reliability Lab — System Architecture

**Version:** 1.0  
**Status:** Approved design; implementation pending

## 1. Project overview

RAG Reliability Lab is a production-style, document-based Retrieval-Augmented Generation (RAG) application with a separate reliability testing framework.

Users can upload, update, delete, search, and ask questions about documents. Answers should be grounded in retrieved document evidence and include source citations.

The reliability framework investigates how document ingestion, version publication, retrieval, and deletion behave when failures or concurrent operations occur.

The project has three primary goals:

1. Build a functioning document-based RAG application.
2. Enforce reliable document lifecycle and retrieval behavior.
3. Reproduce, measure, and document failure scenarios.

The initial research focuses on document lifecycle correctness, not maximizing retrieval relevance.

## 2. Technology stack

| Layer | Technology | Responsibility |
|---|---|---|
| Backend API | Python 3.12, FastAPI | HTTP endpoints and application orchestration |
| Database | PostgreSQL | Authoritative document lifecycle state |
| Vector database | Qdrant | Embedding storage and similarity search |
| Object storage | MinIO / S3 | Original document versions |
| Messaging | Redis Streams | Asynchronous indexing delivery |
| Background processing | Python workers | Parsing, chunking, embedding, indexing |
| Embeddings | Sentence Transformers | Local reproducible embeddings |
| Generation | LLM provider adapter | Evidence-grounded answers |
| Frontend | React, TypeScript | Documents, search, chat, version history |
| Testing | pytest | Unit, integration, concurrency, E2E tests |
| Observability | OpenTelemetry | Traces and operational metrics |
| Infrastructure | Docker Compose | Local development environment |

The backend follows a modular monolith architecture with separate API and worker processes.

## 3. System components

### FastAPI application

Responsible for:

- Authentication and tenant-scoped authorization
- Document upload and update requests
- Document status and version history
- Search and chat endpoints
- Query orchestration
- Health and readiness endpoints

Business logic should remain separate from HTTP route handlers.

### PostgreSQL

Stores authoritative metadata, including:

- Tenants and users
- Document desired and active versions
- Document version history
- Index manifests
- Ingestion jobs
- Transactional outbox events
- Experiment metadata and observations

PostgreSQL determines whether a document version is valid and eligible for retrieval.

### Qdrant

Stores embeddings and chunk metadata for similarity search.

Qdrant is a derived search index, not the authoritative source of document lifecycle state.

Physically stored chunks are not necessarily eligible to appear in application responses.

### Object storage

MinIO stores immutable original document versions locally.

The storage abstraction should support an S3-compatible service later.

### Redis Streams and workers

Redis Streams delivers asynchronous indexing jobs to Python worker processes.

Workers perform parsing, chunking, embedding generation, indexing, and verification.

The system assumes at-least-once delivery. Workers must tolerate duplicate processing.

### Experiment framework

A separate CLI-based framework executes deterministic failure scenarios, checks invariants, collects metrics, and produces reproducible reports.

Fault injection must remain isolated from normal application behavior.

## 4. Document ingestion architecture

### Write path

1. FastAPI authenticates the user and identifies the tenant.
2. The API validates the uploaded file's size and format.
3. The original document is stored in MinIO.
4. PostgreSQL creates a document version and outbox event in one transaction.
5. An outbox dispatcher publishes the indexing job to Redis Streams.
6. A worker parses the document.
7. The worker creates deterministic text chunks.
8. The embedding model produces chunk embeddings.
9. The worker indexes version-specific points in Qdrant.
10. Indexing results are verified against an index manifest.
11. PostgreSQL checks whether the completed version remains the latest desired version.
12. If valid, PostgreSQL atomically publishes it as the active version.
13. Superseded chunks are excluded from retrieval and cleaned up asynchronously.

An uploaded document is not assumed to be immediately searchable.

Once asynchronous ingestion is implemented, uploads and updates return HTTP 202 with an ingestion job ID.

### Transactional outbox

Document metadata and the corresponding outbox event are committed together in PostgreSQL.

This prevents a successful database update from silently losing its indexing request if queue publishing fails.

The dispatcher may publish an event more than once. Consumers must therefore be idempotent.

### Document version states

The planned version lifecycle includes:

- Pending
- Processing
- Retry pending
- Indexed
- Active
- Superseded
- Failed

A completed indexing attempt is activated only if it remains eligible for publication.

Retryable failures return to processing through a retry-pending state.

Terminal failures are explicitly recorded.

Superseded versions become eligible for asynchronous physical cleanup.

A failed replacement must not destroy the last successfully active version.

For document updates, the previous active version may remain searchable while a replacement is processing. The API must report the pending update.

## 5. Retrieval and answer generation

### Read path

1. Authenticate the user and determine their tenant.
2. Embed the query using the indexing-compatible embedding model.
3. Search Qdrant using tenant-level filtering.
4. Retrieve more candidates than the final requested number.
5. Batch-check candidates against PostgreSQL.
6. Reject deleted, superseded, incomplete, or unauthorized evidence.
7. Build a bounded context using the remaining chunks.
8. Generate an answer through the LLM provider adapter.
9. Return the answer with citations to validated source chunks.

If valid evidence is unavailable, the application returns an insufficient-evidence response.

The LLM must not invent source identifiers or citations.

Read-time validation is required even when Qdrant payload filters are used.

Final-answer caching is excluded from the initial implementation.

## 6. PostgreSQL database architecture

| Table | Important fields | Responsibility |
|---|---|---|
| tenants | id, name | Tenant isolation |
| users | id, tenant_id, role | Identity and authorization |
| documents | id, tenant_id, desired_version, active_version, deleted_at | Current document state |
| document_versions | document_id, version, status, object_key, sha256 | Version metadata and lifecycle |
| index_manifests | document_id, version, chunk_count, embedding_model | Expected indexed contents |
| ingestion_jobs | id, document_id, version, status, attempts | Ingestion progress |
| outbox_events | id, event_type, payload, published_at | Durable event dispatch |
| experiment_runs | id, scenario, configuration, started_at | Experiment history |
| experiment_observations | run_id, metric, value, timestamp | Experiment measurements |

Additional timestamps, foreign keys, uniqueness constraints, indexes, and recovery metadata will be specified through SQLAlchemy models and Alembic migrations.

Important requirements:

- Every document belongs to a tenant.
- Document versions are uniquely identified by document ID and version number.
- Original version content and checksums are immutable.
- Processing status may change as ingestion progresses.
- Active version updates must use safe transactional conditions.
- Schema changes require migrations.

## 7. Qdrant data model

One Qdrant point represents one indexed document chunk.

Example payload:

```json
{
  "tenant_id": "tenant-001",
  "document_id": "policy-001",
  "version": 2,
  "chunk_index": 0,
  "text": "Employees can work remotely two days.",
  "content_hash": "sha256:...",
  "embedding_model": "model-v1",
  "index_config_hash": "config-hash"
}
```

Point IDs must be deterministic using document identity, version, chunk index, and indexing configuration.

Qdrant upserts with matching point IDs support idempotent processing.

The embedding dimension must match the selected model and collection configuration.

Document-level completeness and publication correctness are enforced separately from Qdrant upserts.

## 8. HTTP API

| Method | Endpoint | Purpose |
|---|---|---|
| POST | /api/v1/documents | Upload document |
| PUT | /api/v1/documents/{id} | Create new version |
| DELETE | /api/v1/documents/{id} | Delete document |
| GET | /api/v1/documents/{id} | Current state |
| GET | /api/v1/documents/{id}/versions | Version history |
| GET | /api/v1/jobs/{id} | Ingestion status |
| POST | /api/v1/search | Retrieve evidence |
| POST | /api/v1/chat | Generate grounded answer |
| GET | /health/live | Process liveness |
| GET | /health/ready | Dependency readiness |

Once asynchronous ingestion is available, successful upload and update acceptance returns HTTP 202 with an ingestion job ID.

Deletion distinguishes immediate logical revocation from eventual physical cleanup.

The experiment runner is a separate CLI, not a public API.

Request schemas, error contracts, pagination, concurrency preconditions, and exact deletion semantics will be finalized during implementation.

## 9. Reliability invariants

The initial mandatory invariants are:

- INV-01: An older version cannot replace a newer published active version.
- INV-02: Completed replacements cannot expose superseded chunks.
- INV-03: Reprocessing cannot create duplicate logical chunks.
- INV-04: Partially indexed versions cannot become active.
- INV-05: Effective deletion prevents subsequent retrieval.
- INV-06: Tenants cannot retrieve one another's content.
- INV-07: Failed ingestion jobs are observable and recoverable or explicitly terminal.

See `docs/invariants.md` for testable definitions.

Application visibility and physical vector cleanup are different guarantees.

## 10. Reliability experiment architecture

Experiments compare a reliable reference implementation with a controlled faulty variant.

Each experiment specifies:

- Scenario identifier
- Random seed
- Workload and dataset
- System configuration
- Deterministic operation schedule
- Expected behavior
- Invariant assertions
- Repetitions

Initial scenarios:

| ID | Fault | Objective |
|---|---|---|
| F-001 | Skip obsolete-chunk cleanup | Storage vs visibility |
| F-002 | Deliver jobs repeatedly | Idempotency |
| F-003 | Finish older job after newer job | Publication ordering |
| F-004 | Crash worker midway through indexing | Partial-write recovery |
| F-005 | Delete during in-flight queries | Read consistency |
| F-006 | Fail queue publish after database commit | Outbox recovery |

Deterministic worker barriers are preferred before randomized stress tests.

Each experiment begins from a clean known state.

Reports include dependency versions, configuration, dataset, hardware details, and reproduction steps.

Reports must explicitly identify deliberately injected faults.

## 11. Repository architecture

```text
rag-reliability-lab/
├── apps/
│   ├── api/
│   └── web/
├── src/rag_lab/
│   ├── domain/
│   ├── ingestion/
│   ├── retrieval/
│   ├── storage/
│   ├── messaging/
│   └── observability/
├── experiments/
│   ├── faults/
│   ├── scenarios/
│   ├── datasets/
│   └── reports/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── concurrency/
│   └── end_to_end/
├── migrations/
├── infra/
├── docs/
├── compose.yaml
├── pyproject.toml
├── Makefile
└── README.md
```

This is a target structure. Modules should be created when they have an implementation purpose rather than as empty placeholders.

## 12. Implementation phases

### Phase 1 — Foundation and database

Create the Python project, local Docker infrastructure, database models, migrations, application configuration, and initial tests.

### Phase 2 — Core RAG

Implement document storage, parsing, chunking, embeddings, indexing, retrieval, grounded generation, and document updates.

The first complete workflow is:

Create → Index → Search → Update → Search.

Synchronous indexing is acceptable temporarily while building this vertical slice.

### Phase 3 — Reliability architecture

Introduce Redis Streams, workers, transactional outbox, retries, idempotent indexing, atomic version publication, and recovery.

### Phase 4 — Security and retrieval correctness

Complete tenant authorization, read-time validation, deletion guarantees, API hardening, and citation verification.

### Phase 5 — Reliability experiments

Implement deterministic fault injection, invariant checking, experiment repetition, metrics collection, and reproducible reports.

### Phase 6 — Production hardening and public release

Add the user interface, OpenTelemetry, CI, deployment improvements, operational documentation, and release-quality developer workflows.

## 13. v1 exclusions

The initial release deliberately excludes:

- Hybrid retrieval
- Rerankers
- Agentic workflows
- Knowledge graphs
- Kubernetes
- Multi-region replication
- Final-answer caching
- LangChain as a core architectural dependency

These may be revisited only when supported by an explicit engineering or research need.

## 14. Implementation principles

1. Build a working application before introducing distributed failure experiments.
2. Keep PostgreSQL authoritative for document lifecycle state.
3. Treat Qdrant as a derived index.
4. Validate evidence before exposing it.
5. Enforce correctness with transactions, constraints, and tests.
6. Separate experimental faults from normal application behavior.
7. Prefer small, independently testable changes.
8. Measure claimed guarantees instead of assuming them.
9. Document implementation decisions and limitations.
10. Maintain reproducibility throughout development.

This document describes the intended architecture, not a claim that all components or guarantees have already been implemented.
