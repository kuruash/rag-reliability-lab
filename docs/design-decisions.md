# RAG Reliability Lab — Design Decisions

**Version:** 1.0  
**Status:** Initial architectural decisions

## Purpose

This document records significant technical decisions made during the development of RAG Reliability Lab.

Each decision should explain:

- The problem being solved.
- The selected approach.
- Why the approach was chosen.
- Important tradeoffs.
- Conditions under which we might reconsider it.

Accepted decisions should not be changed silently during implementation.

## ADR-001 — Modular monolith with separate workers

**Status:** Accepted

**Decision:** Use one Python application codebase with a FastAPI process and separate background worker processes.

**Reasoning:**

- Clear separation of HTTP requests and asynchronous ingestion.
- Shared domain models and business logic.
- Simpler development and deployment than microservices.
- Easier end-to-end testing and debugging.

**Tradeoff:** Components share a repository and release lifecycle.

**Reconsider if:** Independent scaling or deployment requirements justify splitting services.

## ADR-002 — PostgreSQL as source of truth

**Status:** Accepted

**Decision:** Store authoritative document lifecycle, version, deletion, and ingestion state in PostgreSQL.

**Reasoning:**

- Transactional document state updates.
- Strong relational constraints.
- Independently verifiable version history.
- Explicit control over version publication.

**Tradeoff:** Retrieval requires additional validation against PostgreSQL.

**Rejected approach:** Relying entirely on vector database metadata for document lifecycle correctness.

## ADR-003 — Qdrant as derived vector index

**Status:** Accepted

**Decision:** Use Qdrant for vector similarity search and chunk storage, not as the authoritative source of document validity.

**Reasoning:**

- Specialized vector search functionality.
- Version-specific chunk indexing.
- Deterministic point identifiers.
- Ability to independently inspect stored and visible evidence.

**Tradeoff:** Index state and PostgreSQL state must be coordinated.

## ADR-004 — MinIO for local source storage

**Status:** Accepted

**Decision:** Store original document versions in MinIO locally and support S3-compatible storage later.

**Reasoning:**

- Preserve original source files.
- Keep immutable document versions.
- Enable reproducible reprocessing.
- Separate original data from generated vector indexes.

**Tradeoff:** Object storage introduces an additional dependency and requires orphan-object cleanup handling.

## ADR-005 — Redis Streams for background jobs

**Status:** Accepted

**Decision:** Use Redis Streams with consumer groups for asynchronous ingestion.

**Reasoning:**

- Supports consumer groups.
- Supports pending-message recovery.
- Provides opportunities to test duplicate delivery and worker crashes.
- Fits the initial system's operational complexity.

**Tradeoff:** Processing may happen multiple times. We must implement idempotent workers.

**Rejected for v1:** Kafka and a complex distributed messaging architecture.

## ADR-006 — Transactional outbox

**Status:** Accepted

**Decision:** Commit document-version metadata and indexing outbox events in one PostgreSQL transaction.

**Reasoning:**

- Prevents losing a job when database commit succeeds but queue publishing fails.
- Allows dispatcher recovery.
- Makes the dual-write problem explicit and testable.

**Tradeoff:** Requires an additional dispatcher, event tracking, and duplicate-delivery handling.

## ADR-007 — Version-aware publication

**Status:** Accepted

**Decision:** Index new versions separately and publish an active-version pointer only after successful verification.

**Reasoning:**

- Prevents partial versions from becoming visible.
- Protects against out-of-order worker completion.
- Preserves the last successfully indexed version during failed replacements.

**Tradeoff:** Old and new versions may temporarily coexist physically in Qdrant.

## ADR-008 — Read-time evidence validation

**Status:** Accepted

**Decision:** Validate retrieved chunks against current PostgreSQL state before providing them to users or the LLM.

**Reasoning:**

- Prevents stale evidence exposure after replacement.
- Supports logical deletion.
- Provides tenant authorization checks independent of vector payload metadata.

**Tradeoff:** Adds database queries, retrieval latency, and potential candidate shortages.

We will measure these costs rather than assume they are negligible.

## ADR-009 — Deterministic fault injection

**Status:** Accepted

**Decision:** Use isolated, deterministic experiments with controlled worker barriers before randomized stress testing.

**Reasoning:**

- Repeatable failure reproduction.
- Precise ordering of concurrent operations.
- Easier debugging and comparison.
- Clearer public evidence.

**Tradeoff:** Deterministic schedules do not cover every possible real-world execution.

Randomized stress testing can be introduced later.

## ADR-010 — Docker Compose first

**Status:** Accepted

**Decision:** Use Docker Compose for the initial local environment.

**Reasoning:**

- Reproducible service setup.
- Lower infrastructure complexity.
- Suitable for local integration and fault testing.

**Tradeoff:** Docker Compose is not a complete production orchestration or high-availability solution.

**Rejected for v1:** Kubernetes and multi-region deployment.

## ADR-011 — Explicit Python interfaces instead of a core RAG framework

**Status:** Accepted

**Decision:** Implement explicit Python interfaces for ingestion, embedding, storage, retrieval, and generation.

**Reasoning:**

- Transparent control over system behavior.
- Easier instrumentation.
- Precise failure injection.
- Reduced dependence on framework-specific abstractions.

**Rejected for v1:** Making LangChain the core architecture.

Adapters can be added later if needed.

## ADR-012 — Document correctness before retrieval optimization

**Status:** Accepted

**Decision:** Prioritize lifecycle correctness, version consistency, authorization, deletion, and recovery over advanced retrieval quality features.

**Deferred:**

- Hybrid search.
- Rerankers.
- Knowledge graphs.
- Agentic retrieval.
- Final-answer caching.

**Reasoning:** These features introduce additional variables that could obscure the initial reliability experiments.

## ADR-013 — Six-phase development sequence

**Status:** Accepted

**Decision:** Implement the system in the following order:

1. Repository and database foundation.
2. Working RAG application.
3. Asynchronous reliability architecture.
4. Security and retrieval correctness.
5. Deterministic reliability experiments.
6. Production hardening and public release.

**Reasoning:** A working application is required before meaningful reliability experiments can be performed.

## ADR-014 — Standalone open-source framework deferred

**Status:** Accepted

**Decision:** Publish the application and its experiment suite as one monorepo.

Do not extract a standalone reliability-testing framework until experiments demonstrate reusable value and external demand.

**Reasoning:** Premature abstraction would increase development cost before the useful general-purpose interfaces are understood.

## Open design questions

The following decisions are not yet finalized:

1. Exact concurrency contract for simultaneous document updates.
2. Exact visibility guarantee for retrieval requests overlapping deletion.
3. Ingestion retry limits, backoff, and timeout budgets.
4. Physical cleanup deadline.
5. Index manifest verification method.
6. Specific Sentence Transformers model and revision.
7. LLM provider and generation configuration.
8. Authentication implementation for publicly accessible deployments.
9. Backup, retention, and recovery objectives.
10. Release deployment environment.

These questions should be resolved when the relevant implementation phase begins.

## Decision change procedure

When a significant change is proposed:

1. Identify the existing architectural decision.
2. Explain the problem or new evidence.
3. Describe the proposed alternative.
4. Evaluate benefits, drawbacks, and migration impact.
5. Obtain project-owner approval.
6. Update this document and other affected specifications.
7. Add or update tests when the change affects correctness.

Implementation code must not silently redefine accepted architectural decisions.
