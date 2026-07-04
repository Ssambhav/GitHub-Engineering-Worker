# Memory Object Contract Specification

Memory object contracts define structured execution knowledge before runtime storage exists. A memory object is authoritative only when it is schema-valid, owner-scoped, provenance-linked, versioned, and governed by retention policy.

The canonical memory architecture is [memory/MEMORY.md](../../memory/MEMORY.md).

## Required Fields

Every memory object family must define:

```yaml
object_type: stable canonical type
purpose: why this object exists
owner: agent or subsystem responsible for semantic correctness
schema_ref: schema identifier and version
lifecycle:
  created_by:
    - agent or subsystem
  update_modes:
    - replace | append | merge | supersede | annotate
  terminal_states:
    - active | superseded | archived | expired | deleted
permissions:
  read:
    - permission ids or agent roles
  write:
    - permission ids or owner roles
  delete:
    - policy or owner roles
retention:
  class: transient | session | workflow | repository | long_term | audit_linked
  expiry: policy-owned value
  archival: policy-owned rule
validation:
  schema:
    - required schema checks
  integrity:
    - provenance, hash, and relationship checks
  consistency:
    - cross-object checks
relationships:
  parents:
    - object types
  children:
    - object types
  evidence:
    - artifact, audit, file, issue, tool, or memory refs
compaction:
  eligible: true | false
  rules:
    - summary and evidence preservation rules
promotion:
  eligible: true | false
  target_memory_type: repository | long_term | none
```

## Common Envelope

All schemas should compose the common memory envelope:

```yaml
memory_object_id: string
object_type: string
schema_version: string
workflow_id: string
repository_ref: string
issue_ref: string
owner: string
created_at: timestamp
updated_at: timestamp
version: integer
status: draft | active | superseded | archived | expired | deleted
sensitivity: public | internal | private | secret_ref
retention_class: transient | session | workflow | repository | long_term | audit_linked
confidence:
  level: high | medium | low | unknown
  rationale: string
provenance:
  source_refs:
    - string
  created_by: string
  mutation_refs:
    - string
relationships:
  parent_refs:
    - string
  child_refs:
    - string
  supersedes_refs:
    - string
  related_refs:
    - string
validation:
  schema_valid: boolean
  integrity_valid: boolean
  last_validated_at: timestamp
```

## Mutation Contract

Every mutation must produce a mutation record:

```yaml
mutation_id: stable id
memory_object_id: object id
base_version: integer
new_version: integer
operation: create | update | append | merge | supersede | archive | expire | delete | restore
actor: agent, subsystem, or tool id
reason: concise reason
changed_fields:
  - field paths
source_refs:
  - evidence refs
audit_refs:
  - audit refs
created_at: timestamp
idempotency_key: optional stable key
```

## Contract Quality Checklist

- Is the object family distinct from existing memory families?
- Is the owner responsible for semantic correctness?
- Are immutable fields and legal update modes explicit?
- Are read, write, delete, and sensitive access permissions scoped?
- Can the object be schema validated without runtime reasoning?
- Are provenance and evidence refs sufficient to reconstruct the claim?
- Are retention, compaction, and promotion rules explicit?
- Are conflicts and stale repository revisions detectable?
- Can checkpoints pin object versions for recovery?
- Is the contract reusable beyond GitHub Engineering Worker when practical?
