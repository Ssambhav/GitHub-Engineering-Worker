# Tool Contract Specification

Every tool in GitHub Engineering Worker must be specified by a contract before implementation. A tool contract defines what the tool may do, what it must never do, how it is invoked, how it reports results, and how failures affect autonomous decision making.

The canonical Tool Framework is [TOOLS.md](../../TOOLS.md).

## Required Fields

### Name

Stable human-readable tool name. The registry also assigns a canonical `tool_id`.

### Purpose

One concise statement describing why the tool exists.

### Responsibilities

Specific operations the tool owns. Responsibilities must be externally observable through outputs, side effects, or audit records.

### Non-Responsibilities

Operations the tool must not perform, especially adjacent work owned by another tool category.

### Inputs

Schema-defined input object, including required and optional fields, size limits, path scope, command scope, resource constraints, and idempotency key when relevant.

### Outputs

Schema-defined result object, artifact references, evidence references, side effect summaries, confidence impact, and failure details when applicable.

### Preconditions

Conditions that must be true before execution, such as permissions, locks, repository access, tool dependencies, or approved plans.

### Postconditions

Conditions guaranteed after success or failure. Postconditions must describe side effects and cleanup expectations.

### Permissions Required

Exact permissions required to execute the tool. Permissions should include scope and side-effect class.

### Expected Execution Time

Short, medium, long, or variable, with category-specific expectations where useful.

### Failure Conditions

Known failure modes mapped to the shared failure taxonomy.

### Retry Policy

Whether retry is safe, unsafe, requires changed input, requires an idempotency key, or should route to recovery/escalation.

### Timeout Policy

Default timeout class, maximum timeout, heartbeat expectations, and timeout failure category.

### Idempotency

One of:

- idempotent: repeated execution with same input is safe.
- conditionally_idempotent: safe only with constraints such as idempotency keys, base hashes, or unchanged state.
- non_idempotent: repeated execution may produce additional side effects.

### Safety Constraints

Rules that prevent unsafe behavior, such as path containment, command allowlists, network restrictions, secret redaction, output limits, and lock requirements.

### Validation Rules

Input, output, permission, scope, side-effect, and semantic validation rules.

### Audit Requirements

Events and evidence that must be recorded, including invocation metadata, side effects, failures, redaction status, and result references.

### Confidence Impact

How successful, partial, or failed execution should affect workflow confidence.

### Dependencies

Runtime services, local binaries, APIs, stores, indexes, credentials, or other tools required for operation.

### Recovery Strategy

Recommended response to expected failures, including narrower scope, alternate tool, refreshed state, changed input, retry with backoff, or escalation.

## Contract Template

```yaml
name: Tool Name
tool_id: category.capability.operation
version: contract version
category: Repository | GitHub | File System | Search | Code Modification | Validation | Testing | Git | Memory | Audit | State | Utility | System

purpose: >
  One sentence explaining the tool's reason to exist.

responsibilities:
  - Concrete operation owned by the tool.

non_responsibilities:
  - Adjacent operation the tool must not perform.

inputs:
  schema_ref: schema identifier
  required:
    - field
  optional:
    - field
  limits:
    max_input_size: policy-owned value
    allowed_scope: repository/path/command/network scope

outputs:
  schema_ref: schema identifier
  artifacts:
    - produced artifact type
  evidence:
    - path, command, issue, log, or audit refs
  side_effects:
    - none | read | write | execute | network | state | memory | audit

preconditions:
  - Required permission or state.

postconditions:
  success:
    - Guarantee after successful execution.
  failure:
    - Guarantee after failed execution.

permissions_required:
  - permission id with scope

expected_execution_time: short | medium | long | variable

failure_conditions:
  - category: Timeout | Invalid Input | Permission Denied | Missing File | Repository Error | Network Error | Tool Crash | Malformed Output | Validation Failure | Unexpected Exception | Resource Exhaustion | Dependency Failure
    severity: info | warning | error | critical
    recoverability: retryable | retry_with_changes | not_retryable | escalate

retry_policy:
  safe_to_retry: true | false | conditional
  requires_changed_input: true | false
  idempotency_required: true | false
  backoff: none | fixed | exponential | policy_defined

timeout_policy:
  default: policy-owned value
  maximum: policy-owned value
  heartbeat_required_after: policy-owned value

idempotency: idempotent | conditionally_idempotent | non_idempotent

safety_constraints:
  - Constraint enforced before or during execution.

validation_rules:
  input:
    - Input validation rule.
  output:
    - Output validation rule.
  semantic:
    - Domain validation rule.

audit_requirements:
  level: none | metadata | full | security_sensitive
  events:
    - invocation_started
    - invocation_completed
    - invocation_failed
  fields:
    - correlation_id
    - actor
    - tool_id
    - version
    - scope
    - side_effects

confidence_impact:
  success: expected confidence effect
  partial: expected confidence effect
  failure: expected confidence effect

dependencies:
  - dependency identifier or class

recovery_strategy:
  - Recommended recovery action.
```

## Contract Quality Checklist

- Does the tool own exactly one capability?
- Are all side effects declared?
- Are permissions minimal and scoped?
- Are unsafe paths, commands, and network operations constrained?
- Are outputs schema-validatable?
- Are failure categories mapped to retry behavior?
- Is idempotency explicit?
- Is audit sufficient to reconstruct the invocation?
- Can the tool be discovered by capability without agent changes?
- Is there a retirement path if the tool is replaced?
