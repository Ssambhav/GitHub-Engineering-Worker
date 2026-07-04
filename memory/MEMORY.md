# GitHub Engineering Worker Memory System

GitHub Engineering Worker uses memory to share structured execution knowledge across agents, workflows, tools, validation, retries, audit, and review. Memory is not conversation history. It is a governed collection of versioned objects that describe what the platform knows, why it knows it, how confident it is, and how that knowledge may be reused.

This document is declarative architecture only. It does not implement storage engines, databases, runtime logic, agents, tools, or business logic.

## Memory Philosophy

Memory exists to reduce repeated reasoning, prevent repeated mistakes, preserve evidence-backed decisions, enable reliable recovery, and improve future execution quality.

Agents must not depend on raw chat transcripts, hidden conversational state, or unstructured logs. Agents read and write structured memory objects with owners, schemas, lifecycles, permissions, retention rules, validation rules, and relationships.

Memory should become more useful as execution progresses:

- Early memory captures issue intent, repository shape, assumptions, and search direction.
- Middle memory captures analysis, planning, decisions, tool evidence, patches, failures, retries, and validation.
- Terminal memory captures final review, escalation packets, lessons, and reusable repository or platform knowledge.
- Persistent memory keeps only curated historical knowledge that is safe and useful beyond the current workflow.

## Architecture

The memory system is a contract-governed subsystem shared by all autonomous workers. GitHub Engineering Worker is the first worker using it, but memory object contracts should remain generic enough for future workers.

Core responsibilities:

- Define canonical memory object schemas.
- Track object ownership, permissions, lifecycle, retention, and relationships.
- Support short-lived execution memory and long-lived curated knowledge.
- Provide queryable evidence for decisions, validation, retries, and audit.
- Support checkpoints, snapshots, compaction, recovery, archival, and deletion.
- Preserve provenance, confidence, and version history.
- Avoid storing secrets, raw private data, or unbounded transcripts.

Non-responsibilities:

- Memory does not execute workflows.
- Memory does not choose lifecycle transitions.
- Memory does not replace audit logs, state management, or tool invocation records.
- Memory does not implement databases, indexes, embeddings, retrieval, or runtime services.
- Memory does not store raw chat history as a primary knowledge source.

## Memory Types

### Working Memory

Short-lived active knowledge used during the current stage or adjacent stages. It holds selected artifacts, open questions, current hypotheses, active confidence values, and immediate next-use context.

Retention: normally expires after checkpoint, stage transition, or compaction unless promoted.

### Execution Memory

Workflow-scoped memory that records what happened during one issue lifecycle: issue brief, repository context, search results, files visited, decisions, validation, failures, retries, and review.

Retention: survives restarts and retries until workflow terminal retention policy applies.

### Context Memory

Reusable context collected for reasoning, such as repository conventions, project structure, language/framework metadata, validation entry points, and ownership hints.

Retention: may be workflow-scoped or promoted to repository memory after validation.

### Repository Memory

Repository-specific historical knowledge: architecture summaries, test commands, style conventions, common failure modes, known generated paths, risky modules, and validated change patterns.

Retention: persistent while repository association remains valid; invalidated by repository revision, manifest, or policy changes.

### Issue Memory

Issue-specific knowledge: normalized issue summary, acceptance criteria, ambiguity list, linked evidence, comments, assumptions, and final resolution.

Retention: workflow-scoped plus optional terminal summary for future related issues.

### Reasoning Memory

Structured reasoning artifacts: hypotheses, accepted root cause, rejected alternatives, evidence maps, confidence changes, and rationale for decisions.

Retention: workflow-scoped; selected lessons may be promoted to long-term memory.

### Planning Memory

Implementation and validation plans, scope boundaries, rollback considerations, risk assessments, expected changed files, and acceptance mapping.

Retention: workflow-scoped; plan patterns may be promoted only after successful validation and review.

### Tool Memory

Bounded records of tool invocations, tool capability observations, command results, known flaky checks, dependency failures, and retry safety notes.

Retention: invocation refs persist through audit/state; reusable tool behavior may be promoted when generalized and non-sensitive.

### Validation Memory

Validation reports, static inspection findings, test commands, test results, skipped checks, residual risks, and evidence-to-acceptance mapping.

Retention: workflow-scoped; repository-level validated command knowledge may persist.

### Retry Memory

Retry attempts, failure classifications, changed strategies, rejected repeated strategies, resume stages, and recovery outcomes.

Retention: workflow-scoped; recurring failure lessons may persist after curation.

### Failure Memory

Failure reasons, impact, root failure category, side effects, recovery status, and prevention guidance.

Retention: workflow-scoped; persistent only when generalized, safe, and useful.

### Audit Memory

Memory-side references to audit entries, decision records, provenance, object mutation history, and evidence references. Audit Memory is not the audit log; it indexes audit evidence relevant to memory objects.

Retention: follows audit policy and references immutable audit records.

### Review Memory

Final engineering review, PR description draft, issue response draft, limitations, changed-file summary, validation evidence, and human-facing outcome.

Retention: terminal workflow retention; reusable lessons may be promoted.

### Long-Term Memory

Curated durable knowledge that has been distilled from workflow outcomes. It includes lessons, repository conventions, platform policies, recurring issue patterns, and validated operational guidance.

Retention: persistent until superseded, archived, or deleted by policy.

### Persistent Memory

Any memory class stored beyond process, agent, workflow, or application restart. Persistent memory must be schema-valid, provenance-linked, retention-classified, and safe to retain.

Retention: policy-owned.

### Session Memory

Memory scoped to a single OpenClaw or worker session. It may help avoid repeated work inside a session but must not be the only source of recoverability.

Retention: expires at session end unless promoted through a validated object.

### Transient Memory

Ephemeral calculations, candidate thoughts, temporary ranking scores, and scratch data. It is not authoritative and should not be used for audit, recovery, or final review.

Retention: expires quickly and is usually excluded from checkpoints.

## Memory Object Families

Each object is defined by the reusable memory object contract in [docs/specifications/memory-object-contract.md](../docs/specifications/memory-object-contract.md). Canonical schema templates live in [schemas/](schemas/).

| Object | Purpose | Owner |
| --- | --- | --- |
| Issue Summary | Normalize issue intent, constraints, acceptance criteria, ambiguity, and assumptions. | Issue Understanding Agent |
| Repository Metadata | Identify repository, revisions, languages, manifests, and access scope. | Repository Context Agent |
| Repository Structure | Summarize directories, modules, ownership hints, generated paths, and entry points. | Repository Context Agent |
| Files Visited | Track read files, ranges, hashes, reasons, summaries, and follow-up pointers. | File Reader Agent |
| Files Modified | Track changed files, base hashes, diff refs, modification reasons, and authorization refs. | Code Modification Agent |
| Search Results | Record queries, scopes, ranked hits, snippets, result counts, and gaps. | Repository Search Agent |
| Analysis Results | Capture hypotheses, evidence maps, rejected alternatives, and confidence. | Root Cause Analysis Agent |
| Root Cause | State confirmed or likely cause, affected behavior, minimal change target, and risks. | Root Cause Analysis Agent |
| Engineering Plan | Define implementation steps, validation plan, scope boundaries, and risk controls. | Planning Agent |
| Generated Patch | Describe proposed edits, expected behavioral impact, changed files, and applicability. | Patch Generation Agent |
| Validation Results | Capture static validation, acceptance mapping, residual risks, and decision. | Validation Agent |
| Test Results | Record commands, environment notes, exit codes, durations, and output refs. | Test Execution Agent |
| Retry Attempts | Track failure category, changed strategy, resume stage, and outcome per attempt. | Retry & Recovery Agent |
| Failure Reasons | Classify failures, side effects, recoverability, prevention notes, and escalation needs. | Retry & Recovery Agent |
| Confidence History | Record confidence fields over time, causes of movement, and evidence refs. | Engineering Orchestrator |
| Tool Invocations | Index tool invocation refs, side effects, evidence, failure category, and retry safety. | Tool Framework |
| Workflow Decisions | Record deterministic transition decisions, criteria, inputs, outcomes, and audit refs. | Engineering Orchestrator |
| Execution Timeline | Order key events, checkpoints, stage transitions, and artifact versions. | State Management Agent |
| Audit Entries | Reference audit events relevant to memory objects and mutations. | Audit Logging Agent |
| Engineering Review | Preserve final review, validation summary, changed files, limitations, and outcome. | Review Generation Agent |
| Escalation Summary | Preserve blocker, human question, evidence, urgency, and recommended options. | Escalation Agent |

## Object Definition Requirements

Every memory object specification must define:

- Purpose: why the object exists.
- Owner: agent, subsystem, or framework that owns creation and semantic correctness.
- Fields: required and optional schema fields.
- Lifecycle: creation, update, merge, checkpoint, archival, expiration, deletion.
- Read Permissions: who may inspect the object and at what sensitivity level.
- Write Permissions: who may create, update, append, merge, or delete.
- Update Rules: legal mutation types, immutable fields, version behavior, and conflict policy.
- Retention Policy: expiry, archival, compaction, promotion, and deletion rules.
- Relationships: parent/child refs, evidence refs, audit refs, supersedes refs, dependency refs.

## Common Fields

All authoritative memory objects must include:

```yaml
memory_object_id: stable unique id
object_type: canonical object type
schema_version: semantic schema version
workflow_id: optional workflow correlation id
repository_ref: optional repository reference
issue_ref: optional issue reference
owner: owning agent or subsystem
created_at: timestamp
updated_at: timestamp
version: monotonic object version
status: draft | active | superseded | archived | expired | deleted
sensitivity: public | internal | private | secret_ref
retention_class: transient | session | workflow | repository | long_term | audit_linked
confidence:
  level: high | medium | low | unknown
  rationale: concise reason
provenance:
  source_refs:
    - artifact, file, issue, tool, audit, or memory refs
  created_by: agent or subsystem id
  mutation_refs:
    - memory mutation refs
relationships:
  parent_refs: []
  child_refs: []
  supersedes_refs: []
  related_refs: []
validation:
  schema_valid: true | false
  integrity_valid: true | false
  last_validated_at: timestamp
```

## Memory Lifecycle

### Creation

Objects are created by their owner when a stage produces evidence-backed knowledge. Draft objects may exist while a stage is in progress. Active objects require schema validation and provenance.

### Update

Updates create a new object version. Immutable fields, provenance, audit refs, and prior versions must remain reconstructable. Updates must explain what changed and why.

### Merge

Merge combines compatible objects into a new version or aggregate object. Merge requires compatible schema versions, non-conflicting authoritative fields, and a conflict policy for divergent claims.

### Snapshot

Snapshot captures a consistent set of memory refs and versions at a point in workflow time. Snapshots support decision review, validation, resume, and audit correlation.

### Checkpoint

Checkpoint stores the memory refs required to resume a workflow safely. Checkpoints are owned by state management but include memory object refs and version pins.

### Recovery

Recovery restores memory from the latest valid checkpoint or snapshot, validates object integrity, marks stale or corrupted refs, and routes unresolved gaps to retry or escalation.

### Archival

Archival moves inactive or terminal memory into lower-access, lower-churn storage while retaining provenance and discoverability according to policy.

### Deletion

Deletion is policy-governed. Deletion may be logical tombstoning, redaction, or physical removal depending on sensitivity and compliance requirements. Audit-linked records must preserve enough metadata to explain deletion without retaining unsafe content.

### Expiration

Expiration applies retention rules automatically. Transient and session objects expire quickly; workflow objects expire after terminal retention; repository and long-term objects expire when invalidated or superseded.

### Compaction

Compaction replaces large or repetitive objects with distilled summaries plus evidence refs. Compaction must not erase required audit evidence, active checkpoint refs, unresolved failures, or validation-critical details.

### Versioning

Objects use semantic schema versions and monotonic object versions. Breaking schema changes require migration contracts. Object readers must declare compatible schema ranges.

### Conflict Resolution

Conflicts occur when two objects make incompatible claims about the same domain. Owners resolve conflicts when within their contract. The orchestrator resolves cross-domain conflicts using evidence, confidence, freshness, and policy. Unsafe unresolved conflicts route to escalation.

## Memory Access

Agents interact with memory through memory tools once implemented. Contracts support these operations:

- Read: fetch an object by id and version.
- Write: create a new object.
- Append: add event-like entries to append-only object families.
- Merge: combine compatible objects under policy.
- Query: search by type, relationship, repository, issue, confidence, lifecycle state, or evidence ref.
- Snapshot: capture a consistent set of object refs and versions.
- Restore: restore refs from a checkpoint or snapshot.
- Lock: acquire object or object-family mutation lock.
- Unlock: release mutation lock with audit metadata.

## Concurrency

Memory is multi-agent and must assume concurrent readers and bounded concurrent writers.

Rules:

- Reads are allowed concurrently unless sensitivity policy blocks access.
- Writes require ownership permission and optimistic version checks.
- Merges require a merge lock or compare-and-swap over all input versions.
- Append-only objects accept concurrent append when sequence ids and idempotency keys are unique.
- Snapshot creation must pin object versions to prevent moving-target recovery.
- Conflicting writes produce a structured conflict object, not silent overwrite.
- Long-running agents must refresh memory before acting on stale versions.

## Ownership

Creation:

- Specialist agents create objects they semantically own.
- The Tool Framework creates tool invocation memory refs.
- State Management creates execution timeline and checkpoint memory refs.
- Audit Logging creates audit reference memory.
- Memory Management may create curated long-term objects after terminal review.

Updates:

- Owners may update their object families.
- The orchestrator may update coordination objects such as confidence history and workflow decisions.
- Memory Management may compact, archive, promote, or annotate memory under policy.

Deletion:

- Memory Management owns deletion workflows.
- Object owners may request deletion or redaction.
- Audit-linked, compliance-sensitive, or human-authored records require policy authorization.

Sensitive reads:

- Secret values must not be stored directly. Store secret references only.
- Sensitive memory requires explicit permission scope.
- Review and escalation outputs must redact private or secret content.

Conflict resolution:

- Object owners resolve same-family conflicts.
- The orchestrator resolves lifecycle-impacting conflicts.
- Security, auditability, or product-intent conflicts escalate.

## Persistence Strategy

Must survive:

- Agent restart: active workflow memory, owner refs, current versions, locks where applicable, and pending work.
- Workflow restart: execution memory, checkpoints, snapshots, retry history, decision history, and validation state.
- Retry: failure memory, retry memory, rejected strategies, confidence history, and affected artifacts.
- Repository reload: repository memory with revision-aware invalidation, current workspace refs, and repository metadata.
- Human escalation: issue memory, evidence refs, blocker summary, escalation question, audit refs, and resume instructions.
- Application restart: persistent memory, checkpoints, snapshots, terminal summaries, and long-term curated knowledge.

Should not persist:

- Raw hidden chain-of-thought or private scratch reasoning.
- Unbounded chat transcripts.
- Secrets or credentials.
- Full command output when a bounded summary and artifact ref suffice.
- Large generated artifacts unless referenced by audit/state policy.
- Transient rankings, temporary prompts, and speculative notes that were not evidence-backed.

## Validation

Every memory object must support:

- Schema validation: required fields, enums, type checks, version compatibility, and size limits.
- Integrity checks: content hashes, evidence ref reachability, version monotonicity, owner validity, and timestamp sanity.
- Duplicate detection: idempotency keys, equivalent source refs, repeated tool invocations, and duplicate search results.
- Conflict detection: incompatible claims, stale repository revisions, contradictory confidence movement, and divergent plans.
- Consistency validation: relationships point to existing compatible objects; workflow, issue, and repository refs align.
- Corruption recovery: quarantine malformed objects, restore from latest valid snapshot, mark missing refs, and escalate when safety cannot be established.

## Checkpoint Strategy

Memory checkpoints are referenced by workflow checkpoints and state snapshots.

Each checkpoint stores:

- Checkpoint id, type, workflow id, stage, timestamp, and creator.
- Repository ref, workspace ref, and revision/content hash.
- Pinned memory object ids and versions required for resume.
- Artifact refs and hashes for issue brief, repository context, file excerpts, plans, patch proposal, applied changes, validation, tests, retries, and review.
- Confidence snapshot.
- Failure and retry refs.
- Tool invocation refs and side-effect summaries.
- Audit refs.
- Locks held, released, or needing cleanup.
- Restoration scope and partial-restore rules.

Capabilities:

- Pause: create checkpoint, release or record locks, record resume stage.
- Resume: validate checkpoint freshness, restore object refs, refresh stale repository refs, and continue at safe stage.
- Rollback: identify restore point and affected side effects; actual rollback is policy/tool-owned.
- Crash Recovery: restore latest valid checkpoint and mark uncertain side effects for audit/recovery.
- Partial Restoration: restore selected object families when only one family is corrupted or stale.

## Best Practices

- Store structured facts, not transcripts.
- Prefer references to large evidence over copying large content.
- Record confidence changes with evidence and reason.
- Promote knowledge only after validation or terminal review.
- Keep repository memory revision-aware.
- Treat failure memory as a first-class learning source.
- Compact after decision points, not before validation-critical evidence is stable.
- Redact before review, escalation, and long-term retention.
- Make every durable object schema-valid, provenance-linked, and owner-scoped.

## Extension Guide

To add a new memory object family:

1. Confirm no existing object family covers the knowledge.
2. Write a memory object contract using [Memory Object Contract](../docs/specifications/memory-object-contract.md).
3. Add or extend a schema template under [schemas/](schemas/).
4. Define owner, permissions, lifecycle, retention, and validation.
5. Declare relationships to existing objects.
6. Add checkpoint and snapshot participation rules if the object affects recovery.
7. Define compaction and promotion behavior.
8. Add examples to [contracts/](contracts/) when the family is reusable.
9. Keep the design declarative until runtime implementation is explicitly scoped.
