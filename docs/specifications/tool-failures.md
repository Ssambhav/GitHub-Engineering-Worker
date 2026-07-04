# Tool Failure Specification

All tools in GitHub Engineering Worker use a shared failure taxonomy. Structured failures allow the orchestrator and Retry & Recovery Agent to distinguish transient problems from unsafe conditions, contract violations, and human escalation needs.

The canonical Tool Framework is [TOOLS.md](../../TOOLS.md).

## Failure Response Shape

```yaml
failure:
  category: Timeout | Invalid Input | Permission Denied | Missing File | Repository Error | Network Error | Tool Crash | Malformed Output | Validation Failure | Unexpected Exception | Resource Exhaustion | Dependency Failure
  severity: info | warning | error | critical
  recoverability: retryable | retry_with_changes | not_retryable | escalate
  message: bounded diagnostic
  details_ref: optional log or artifact ref
  side_effects_committed:
    - optional side effect refs
retry:
  recommended: true | false
  safe_to_retry: true | false
  requires_changed_input: true | false
  backoff_hint: optional
audit_refs:
  - audit event refs
```

## Failure Categories

### Timeout

Severity: warning or error.

Recoverability: retryable when idempotent; retry_with_changes when scope or resources caused the timeout.

Retry behavior: retry with backoff, narrower scope, or longer timeout only if policy allows.

Audit requirements: record duration, timeout class, partial output, and side effects.

Escalation: escalate after repeated timeouts or unsafe partial side effects.

### Invalid Input

Severity: error.

Recoverability: not_retryable until input changes.

Retry behavior: do not retry the same request.

Audit requirements: record validation rule failures and requesting agent.

Escalation: escalate if the contract mismatch blocks the workflow.

### Permission Denied

Severity: error or critical.

Recoverability: not_retryable without permission change.

Retry behavior: do not retry unchanged.

Audit requirements: record denied permission, scope, subject, and tool id.

Escalation: escalate when permission is required to continue.

### Missing File

Severity: warning or error.

Recoverability: retry_with_changes.

Retry behavior: retry only after refreshed search, corrected path, or state update.

Audit requirements: record path, repository ref, and state snapshot.

Escalation: escalate if a required file is absent or repository state is inconsistent.

### Repository Error

Severity: error.

Recoverability: retryable or retry_with_changes.

Retry behavior: refresh repository state, verify locks, retry if transient.

Audit requirements: record repository ref, operation, state, and error class.

Escalation: escalate on persistent corruption, lock conflict, or unsafe dirty state.

### Network Error

Severity: warning or error.

Recoverability: retryable.

Retry behavior: retry with backoff if operation is idempotent.

Audit requirements: record endpoint class, status class, and retry count. Do not record secrets.

Escalation: escalate if the external service blocks required progress.

### Tool Crash

Severity: error or critical.

Recoverability: retryable once or escalate.

Retry behavior: retry only when crash appears transient and side effects are safe.

Audit requirements: record tool version, input hash, crash ref, and side effects.

Escalation: escalate repeated crashes or security-sensitive crashes.

### Malformed Output

Severity: error.

Recoverability: retryable if transient; otherwise not_retryable.

Retry behavior: retry once only when safe; otherwise treat as contract violation.

Audit requirements: record output schema errors and tool version.

Escalation: escalate persistent malformed output or contract mismatch.

### Validation Failure

Severity: warning or error.

Recoverability: retry_with_changes.

Retry behavior: retry only with corrected input, output, environment, or implementation strategy.

Audit requirements: record failed validation rule and artifact refs.

Escalation: escalate when validation policy cannot be satisfied.

### Unexpected Exception

Severity: error or critical.

Recoverability: unknown.

Retry behavior: treat as unsafe; retry only under policy and when side effects are known.

Audit requirements: record bounded diagnostic, tool version, and details ref.

Escalation: escalate if cause remains unknown after one recovery attempt.

### Resource Exhaustion

Severity: error.

Recoverability: retry_with_changes.

Retry behavior: retry with smaller scope, reduced output, or approved higher resources.

Audit requirements: record resource class, limit, and request scope.

Escalation: escalate when resource needs exceed policy.

### Dependency Failure

Severity: warning or error.

Recoverability: retryable or escalate.

Retry behavior: retry after dependency recovery, select alternate tool, or narrow operation.

Audit requirements: record dependency identity, failure class, and fallback attempts.

Escalation: escalate if no alternate exists and dependency blocks work.

## Severity Definitions

- info: non-blocking diagnostic.
- warning: operation degraded or partial but workflow may continue.
- error: operation failed and requires recovery, retry, changed input, or alternate path.
- critical: unsafe, security-sensitive, or state-threatening failure.

## Recoverability Definitions

- retryable: safe to retry under the same intent, usually with backoff.
- retry_with_changes: retry only after changed input, narrowed scope, refreshed state, or new strategy.
- not_retryable: retry would repeat the same failure or create risk.
- escalate: human or operator decision is required.

## Audit Expectations

Every failed invocation should record enough information to reconstruct:

- Tool identity and version.
- Requesting agent.
- Correlation id.
- Input scope or input hash.
- Failure category and severity.
- Side effects committed.
- Retry recommendation.
- Redaction status.

Secrets and large raw outputs must be stored only through approved redacted artifact references.
