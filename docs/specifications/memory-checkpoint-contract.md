# Memory Checkpoint Contract Specification

Memory checkpoints pin the memory required to pause, resume, rollback-plan, crash recover, or partially restore an autonomous workflow.

## Checkpoint Contract

```yaml
checkpoint_id: stable id
checkpoint_type: intake | understanding | context | evidence | analysis | plan | patch | modification | validation | decision | terminal | custom
workflow_id: workflow correlation id
stage_id: workflow stage at checkpoint time
created_at: timestamp
created_by: agent or subsystem id
repository:
  repository_ref: optional repository ref
  workspace_ref: optional workspace ref
  revision: optional commit or content hash
issue_ref: optional issue ref
memory_refs:
  - object_id: memory object id
    version: pinned version
    required_for_resume: true | false
artifact_refs:
  - artifact id or path ref
confidence_snapshot:
  issue_understanding: high | medium | low | unknown
  repository_context: high | medium | low | unknown
  root_cause: high | medium | low | unknown
  plan: high | medium | low | unknown
  patch: high | medium | low | unknown
  validation: high | medium | low | unknown
  overall: high | medium | low | unknown
retry:
  count: integer
  last_failure_ref: optional ref
tool_invocation_refs:
  - ref
audit_refs:
  - ref
locks:
  held:
    - lock refs
  released:
    - lock refs
  cleanup_required:
    - obligation refs
restore:
  resume_stage: stage id
  partial_restore_allowed: true | false
  stale_ref_policy: refresh | quarantine | escalate
```

## Restoration Rules

- Validate checkpoint schema before restore.
- Validate repository revision and workspace freshness.
- Restore pinned memory versions, not latest versions, unless policy requests refresh.
- Mark missing, corrupted, or stale objects explicitly.
- Recompute confidence only after refreshed evidence is available.
- Escalate when required resume memory cannot be restored safely.
