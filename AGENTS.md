# RAG Reliability Lab — Agent Instructions

## Project purpose

RAG Reliability Lab is a production-style document RAG application and reliability experimentation framework.

The project investigates document lifecycle consistency, version publication, retrieval correctness, asynchronous processing, failure recovery, and tenant isolation.

The initial focus is reliability, not advanced retrieval features.

## Required project context

Before making architectural or significant implementation changes, read:

- `docs/architecture.md` — System architecture and component responsibilities.
- `docs/invariants.md` — Reliability guarantees and verification requirements.
- `docs/design-decisions.md` — Accepted decisions and open questions.

Use the relevant sections rather than repeatedly reading unrelated documentation.

The documented architecture is the current design reference.

## Engineering workflow

For every implementation task:

1. Inspect the relevant existing code.
2. Identify the smallest implementation that satisfies the requirement.
3. Explain significant design changes or tradeoffs.
4. Implement only the requested scope.
5. Add appropriate automated tests.
6. Run relevant linting, formatting, and tests.
7. Report what changed, what passed, and what remains unverified.

Do not claim a test passed unless it was executed successfully.

Do not claim an invariant is verified without supporting tests.

## Architecture rules

- Use Python 3.12 for the initial backend target.
- Use FastAPI for HTTP APIs.
- Use PostgreSQL as the authoritative document lifecycle store.
- Use Qdrant for vector indexing and similarity search.
- Use MinIO/S3-compatible storage for original document versions.
- Use Redis Streams for asynchronous job delivery when Phase 3 begins.
- Keep the API and workers as separate processes in one modular codebase.
- Keep HTTP routes thin.
- Separate domain logic, storage interfaces, and infrastructure implementations.
- Avoid unnecessary abstraction and premature microservices.

## Document lifecycle rules

- A document may have a desired version and a separately active version.
- Never replace a newer published version with an older one.
- Never publish an incomplete indexing attempt.
- Failed replacements must preserve the last valid active version.
- Reprocessing must not create duplicate logical chunks.
- Deletion must revoke retrieval visibility according to the documented deletion contract.
- Physical Qdrant cleanup may be asynchronous.
- Use safe PostgreSQL transactions and conditions for state transitions.

Review `docs/invariants.md` for detailed guarantees.

## Retrieval rules

- Derive tenant identity from trusted authentication.
- Apply tenant filtering to vector searches.
- Validate retrieved document versions and authorization in PostgreSQL.
- Never expose deleted, superseded, or unauthorized evidence.
- Construct LLM context only from validated evidence.
- Ground citations in actual retrieved source chunks.
- Return an insufficient-evidence response when supported evidence is unavailable.
- Treat retrieved text as untrusted input.

## Database rules

- Use SQLAlchemy and Alembic for relational persistence and migrations.
- Enforce appropriate primary keys, foreign keys, and uniqueness constraints.
- Use transactions for authoritative lifecycle updates.
- Do not modify the database schema without a migration.
- Do not delete or rewrite migration history casually.
- Do not delete production or user data without explicit authorization.

## Testing rules

- Write unit tests for pure domain and transformation logic.
- Write integration tests for database and storage behavior.
- Write concurrency tests for version publication and deletion races.
- Write fault-injection tests in the experiment framework.
- Keep tests reproducible and isolated.
- Do not weaken an invariant or test assertion merely to make a test pass.
- Use disposable data and isolated infrastructure for destructive experiments.

## Code quality

- Prefer readable, typed Python code.
- Follow the repository's Ruff configuration.
- Use descriptive function and variable names.
- Prefer explicit behavior over hidden framework magic.
- Handle errors consistently.
- Avoid broad exception suppression.
- Never hardcode secrets.
- Document non-obvious concurrency and reliability logic.

## Scope management

Follow the six implementation phases in `docs/architecture.md`.

Do not implement later-phase infrastructure without a concrete requirement.

Do not introduce the following into v1 without approval:

- LangChain as the core framework.
- Kubernetes.
- Kafka.
- Hybrid search.
- Rerankers.
- Agentic workflows.
- Multi-region replication.
- Final-answer caching.

Do not generate empty placeholder modules solely to match the target directory structure.

## Experiment safety

- Keep fault injection separate from normal application logic.
- Never expose destructive experiment controls through public application endpoints.
- Run destructive experiments only in isolated environments.
- Record configuration, seeds, dependency versions, and expected behavior.
- Clearly label intentionally injected failures.
- Do not present simulated failures as discovered third-party software defects.

## Git workflow

- Work on feature branches for significant changes.
- Keep commits focused.
- Inspect diffs before commits.
- Do not force-push, rewrite history, or delete branches without approval.
- Do not commit secrets, local environment files, generated datasets, or temporary reports unless explicitly intended.

## When uncertain

If a requested change conflicts with an accepted architectural decision, explain the conflict before implementing it.

If an implementation detail remains undecided, propose a reasonable option and explain its tradeoffs.

Do not silently invent product requirements, reliability guarantees, or architectural decisions.

## Completion report

After an implementation task, provide:

- Files created or modified.
- Behavior implemented.
- Tests executed and their results.
- Architecture or invariant implications.
- Remaining limitations or follow-up work.

The objective is a testable, understandable engineering system, not simply generating code quickly.
