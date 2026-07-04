# Retry Escalation Report

Workflow: `{{workflow_id}}`
Issue: `{{issue_ref}}`
Repository: `{{repository_ref}}`

## Escalation Reason

`{{failure_type}}` at `{{failed_stage}}` requires escalation because `{{escalation_trigger}}`.

## Attempts

- Attempt count: `{{attempt_count}}`
- Strategies tried: `{{strategy_refs}}`
- Repeated failure detected: `{{repeated_failure}}`

## Safety Status

- Repository safety: `{{repository_safety_status}}`
- State integrity: `{{state_integrity_status}}`
- Side effects known: `{{side_effects_known}}`
- Cleanup required: `{{cleanup_required}}`

## Validation Status

`{{validation_summary}}`

## Decision Needed

`{{human_or_operator_question}}`

## Evidence

- Failure analysis: `{{failure_analysis_ref}}`
- Retry history: `{{retry_history_refs}}`
- Validation/test refs: `{{validation_refs}}`
- Audit refs: `{{audit_refs}}`
