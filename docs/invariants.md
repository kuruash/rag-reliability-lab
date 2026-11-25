# RAG Reliability Lab — Reliability Invariants

**Version:** 1.0  
**Status:** Planned guarantees; verification pending

## Purpose

This document defines the reliability properties that RAG Reliability Lab intends to enforce.

An invariant is a condition that must remain true during normal operation and under the stated failure conditions.

Each invariant must have automated tests before being considered verified.

A passing test under one scenario does not prove correctness under every possible concurrent execution.

## INV-01 — Monotonic version publication

**Requirement:** An older version must not replace a newer successfully published active version.

Example:

1. Upload version 1.
2. Delay its ingestion worker.
3. Upload version 2.
4. Complete and publish version 2.
5. Allow version 1's worker to finish.

Expected result:

- Active version remains 2.
- Version 1 cannot overwrite the active-version pointer.

Implementation mechanism:

- Atomic PostgreSQL updates.
- Conditional publication.
- Verification against the latest desired version.

Primary test: F-003.

## INV-02 — No superseded evidence after publication

**Requirement:** Once a replacement version has been published successfully, normal retrieval must not expose chunks from superseded versions.

Example:

1. Version 1 is active.
2. Version 2 is indexed and published.
3. Qdrant temporarily retains version 1 chunks.
4. A user performs a search.

Expected result:

- Application retrieval returns eligible version 2 chunks.
- Version 1 chunks do not appear.
- Physical cleanup may happen later.

Implementation mechanism:

- PostgreSQL version validation at retrieval time.
- Rejection of superseded candidates.

Primary test: F-001 and version replacement integration tests.

## INV-03 — Idempotent indexing

**Requirement:** Reprocessing the same version and indexing configuration must not produce duplicate logical chunks.

Example:

1. An indexing job is delivered.
2. The worker indexes the document.
3. The same job is delivered again.

Expected result:

- Only one logical point exists per document, version, indexing configuration, and chunk index.
- Duplicate processing does not alter the authoritative document state incorrectly.

Implementation mechanism:

- Deterministic Qdrant point IDs.
- Idempotent worker operations.
- Appropriate database uniqueness constraints.

Primary test: F-002.

## INV-04 — No partial version publication

**Requirement:** An incomplete indexing attempt must never become an active document version.

Example:

1. A document requires 20 chunks.
2. The worker successfully writes 8 chunks.
3. The worker crashes.

Expected result:

- The incomplete version is not published.
- The previously active version remains available when applicable.
- The interrupted job can recover or fail explicitly.

Implementation mechanism:

- Index manifest verification.
- Version-specific indexing.
- Atomic publication in PostgreSQL.

Primary test: F-004.

## INV-05 — Effective deletion prevents retrieval

**Requirement:** Once document deletion has become effective, the application must not expose that document through subsequent retrieval.

Example:

1. A document is active.
2. A deletion request is accepted and logical revocation completes.
3. Qdrant still contains its chunks.
4. A retrieval request executes after effective deletion.

Expected result:

- The deleted document is not returned.
- Physical cleanup can complete asynchronously.

Implementation mechanism:

- Authoritative deletion state in PostgreSQL.
- Read-time evidence validation.
- Explicit synchronization or final validation for overlapping reads.

Primary test: F-005.

The exact concurrency boundary for requests already in flight must be specified and tested before claiming stronger deletion consistency.

## INV-06 — Tenant isolation

**Requirement:** A user belonging to Tenant A must not retrieve Tenant B's document content.

Expected behavior:

- Tenant-scoped authentication and authorization.
- Tenant-filtered vector searches.
- Independent authorization checks against PostgreSQL.
- No cross-tenant source text in search results or LLM prompts.

Implementation mechanism:

- Trusted tenant identity derived from authentication.
- Tenant relationships enforced in PostgreSQL.
- Tenant filters in Qdrant.
- Authorization validation before evidence exposure.

Primary tests:

- Cross-tenant search.
- Cross-tenant document lookup.
- Cross-tenant chat.
- Tampered or forged tenant identifiers.

## INV-07 — Observable and recoverable failures

**Requirement:** Failed ingestion jobs must not disappear silently.

Every failed job must either:

- Remain eligible for a documented recovery/retry mechanism; or
- Be explicitly marked as a terminal failure.

Expected behavior:

- Job status is persisted.
- Attempts are tracked.
- Failures are recorded.
- Retry limits are enforced.
- Terminal outcomes are visible through the job API.

Implementation mechanism:

- PostgreSQL ingestion job records.
- Redis Streams pending-message recovery.
- Explicit retry and terminal-state handling.

Primary tests: F-004 and F-006.

## Physical cleanup guarantee

Application-level visibility and physical vector deletion are distinct.

A document can be unavailable through the application while obsolete vectors still exist in Qdrant.

We will separately measure:

- Time from supersession or deletion to physical cleanup.
- Number of remaining obsolete chunks.
- Cleanup failures.
- Compliance with a configurable cleanup deadline.

The exact deadline is a configuration decision to be finalized before experiments.

## Testing strategy

Each invariant must have:

1. A reproducible test scenario.
2. A clearly defined initial state.
3. Controlled operations and failure injection where applicable.
4. Assertions against PostgreSQL and application responses.
5. Qdrant inspection where physical state matters.
6. Expected and observed results.
7. Failure diagnostics.

Tests should cover both normal operation and controlled failures.

The experiment runner must distinguish intentionally introduced faults from failures observed in the reference implementation.

## Verification status

| Invariant | Implementation | Automated tests | Verified |
|---|---|---|---|
| INV-01 | Pending | Pending | No |
| INV-02 | Pending | Pending | No |
| INV-03 | Pending | Pending | No |
| INV-04 | Pending | Pending | No |
| INV-05 | Pending | Pending | No |
| INV-06 | Pending | Pending | No |
| INV-07 | Pending | Pending | No |

Update this table only when the implementation and corresponding tests provide supporting evidence.
