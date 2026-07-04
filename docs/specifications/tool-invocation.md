# Tool Invocation Specification

Tool invocation is the controlled execution boundary between agents and the outside world. All tool calls must be schema-validated, permission-checked, audited, timeout-bound, and result-validated.

The canonical Tool Framework is [TOOLS.md](../../TOOLS.md).

## Invocation Types

### Synchronous

Used for short, bounded operations such as file reads, repository metadata inspection, or audit append operations. The response is returned when execution completes or fails.

### Asynchronous

Used for long-running operations such as test execution, large searches, or external API operations. The framework returns an accepted status and emits progress events until completion, failure, timeout, or cancellation.

## Request Format

```yaml
request_id: unique invocation id
correlation_id: workflow id
agent_id: requesting agent
tool_id: canonical tool id or capability selector
tool_version: optional required version or range
capability: optional capability selector
intent: concise reason for invocation
inputs: schema-validated input object
permissions_context:
  subject: agent or workflow identity
  requested_permissions:
    - permission ids
  scope:
    repositories:
      - repo refs
    paths:
      - allowed paths or globs
    commands:
      - approved command refs
constraints:
  timeout: requested timeout
  max_output_size: output budget
  allow_network: true | false
  allow_side_effects: true | false
  idempotency_key: optional key
  cancellation_token: optional token
audit:
  required: true | false
  sensitivity: normal | security_sensitive
  reason: why the tool is needed
expected_output:
  schema_ref: expected output schema
  validation_rules:
    - validation rule
```

## Response Format

```yaml
request_id: original request id
tool_id: executed tool id
tool_version: executed version
status: success | partial | failed | cancelled | timed_out | denied
started_at: timestamp
completed_at: timestamp
duration_ms: elapsed time
outputs: schema-validated output object or artifact refs
side_effects:
  - declared side effects that occurred
evidence:
  - path, command, issue, artifact, or log refs
confidence_impact:
  level: increases | decreases | neutral | blocks
  rationale: evidence-backed explanation
failure:
  category: optional failure category
  severity: info | warning | error | critical
  recoverability: retryable | retry_with_changes | not_retryable | escalate
  message: bounded diagnostic
  details_ref: optional detailed artifact or log ref
retry:
  recommended: true | false
  safe_to_retry: true | false
  requires_changed_input: true | false
  backoff_hint: optional
audit_refs:
  - audit event references
validation:
  input_validated: true | false
  output_validated: true | false
  validation_errors:
    - optional validation error
```

## Execution Stages

1. Resolve tool by id or capability.
2. Validate tool status and version compatibility.
3. Validate request schema.
4. Validate permissions and scope.
5. Validate side effects against current workflow phase.
6. Initialize audit record when required.
7. Execute synchronously or enqueue asynchronous execution.
8. Emit bounded progress events when applicable.
9. Validate output and side effect report.
10. Return structured response.
11. Record completion, failure, timeout, or cancellation.

## Streaming

Streaming is allowed only when the tool contract declares it. Stream chunks must include:

- request id.
- sequence number.
- timestamp.
- chunk type.
- content or artifact ref.
- truncation/redaction status.

Streaming must respect output budgets and secret redaction.

## Cancellation

Cancellation requests should include request id and cancellation token. Tool responses must state whether:

- Execution stopped.
- Side effects occurred.
- Cleanup completed.
- Retry is safe.

Cancellation is best-effort when the underlying operation cannot be interrupted safely.

## Timeouts

Timeouts are mandatory. Effective timeout is resolved from:

1. Explicit invocation constraint.
2. Tool contract default.
3. Policy default.
4. Platform maximum.

Timeout responses must report partial side effects and whether retry is safe.

## Partial Failures

Partial failures must separate:

- Completed operations.
- Failed operations.
- Skipped operations.
- Side effects already committed.
- Cleanup status.

Partial responses should be treated as unsafe for blind retry unless the tool declares idempotency.

## Output Validation

Outputs are validated before delivery to agents. Validation includes schema, size, path containment, redaction, side effect consistency, and category-specific semantic rules.

Malformed output is reported as a Tool Framework failure even if the underlying operation succeeded.

## Error Propagation

Tools must return structured errors using the shared failure taxonomy. Raw stack traces, secrets, and unbounded logs must not be returned directly to agents.
