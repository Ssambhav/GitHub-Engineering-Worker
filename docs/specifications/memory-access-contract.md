# Memory Access Contract Specification

Memory access contracts define how agents and subsystems may read, write, append, merge, query, snapshot, restore, lock, and unlock memory. This specification describes required behavior for future tools and services; it does not implement them.

## Operation Envelope

```yaml
operation_id: stable unique id
operation: read | write | append | merge | query | snapshot | restore | lock | unlock
actor: agent, subsystem, or tool id
workflow_id: optional workflow id
scope:
  repository_ref: optional repository ref
  issue_ref: optional issue ref
  object_types:
    - optional type filters
permissions:
  requested:
    - permission ids
constraints:
  max_results: optional integer
  schema_versions:
    - compatible versions
  consistency: best_effort | checkpoint_consistent | strict
  timeout: policy-owned value
audit:
  required: true | false
  sensitivity: normal | security_sensitive
```

## Operation Results

```yaml
operation_id: original operation id
status: success | partial | failed | denied | conflict | timed_out
objects:
  - memory object refs or inline bounded objects
versions:
  - object id and version
side_effects:
  - memory_read | memory_write | memory_lock | memory_unlock | none
validation:
  input_validated: boolean
  output_validated: boolean
failure:
  category: optional category
  recoverability: retryable | retry_with_changes | not_retryable | escalate
  message: bounded diagnostic
audit_refs:
  - audit refs
```

## Access Rules

- Read operations must enforce sensitivity and scope.
- Write operations require object-family ownership or delegated permission.
- Append operations require sequence or idempotency guarantees.
- Merge operations must validate all input versions and record conflict outcomes.
- Query operations must return bounded results with type, version, confidence, and provenance summaries.
- Snapshot operations must pin object ids and versions.
- Restore operations must validate checkpoint freshness and object integrity.
- Lock operations must declare object family, scope, holder, lease duration, and cleanup behavior.
- Unlock operations must verify holder identity or recovery authority.

## Concurrency Requirements

- Use optimistic version checks for normal updates.
- Use locks for merge, delete, restore, and cross-object mutation.
- Never silently overwrite a newer version.
- Return a structured conflict when base versions differ.
- Treat stale reads as low confidence for modification decisions.
