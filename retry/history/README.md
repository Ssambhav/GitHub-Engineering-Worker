# Retry History

Retry history records every failed attempt and every recovery attempt for a workflow. It prevents duplicate fixes, repeated failures, and infinite loops.

Retry history is workflow-scoped state, with durable learning candidates proposed to the Memory System only when reusable and safe.

## Tracked Fields

- Attempt Number
- Failure Type
- Root Cause
- Modified Files
- Generated Patch
- Tool Outputs
- Validation Results
- Test Results
- Reasoning Summary
- Confidence
- Recovery Strategy
- Execution Time
- Final Outcome

## Anti-Repetition Checks

Before any retry, the retry history must be checked for:

- same failure type with same root cause;
- same tool with same input hash and same failure;
- same prompt without new context;
- same patch or equivalent changed-file diff;
- same failing validation/test evidence;
- same target resume stage with no changed strategy.

If an identical attempt is detected, retry is ineligible and escalation is required unless policy permits a single diagnostic retry for an unknown failure.

## Retention

- Raw logs and patches should be stored as artifact refs, not inline.
- Workflow history remains part of state/audit according to retention policy.
- Reusable lessons may be proposed to memory after terminal outcome.
- Secrets and private raw repository content must not be retained in retry summaries.
