# Agent Contract Specification

Every production agent in GitHub Engineering Worker must define and honor a contract. Contracts are declarative boundaries for ownership, communication, tools, memory, state, failure handling, and auditability.

The complete required agent set is documented in [AGENTS.md](../../AGENTS.md). This specification defines the reusable contract shape for existing and future agents.

## Required Contract Fields

### Identity

Stable agent name and optional version. The identity must be unique across the platform.

### Purpose

One concise statement describing why the agent exists. If the purpose overlaps substantially with another agent, the contract should be rejected or merged.

### Responsibilities

Concrete duties the agent owns. Responsibilities should be observable through artifacts or events.

### Non-Responsibilities

Work the agent must not perform. This field prevents responsibility drift and duplicated engineering work.

### Inputs

Artifact references, inline bounded data, constraints, and context required for execution.

### Outputs

Artifacts, events, confidence reports, and recommendations produced by the agent.

### Dependencies

Other agents, artifact types, policies, configuration, or external systems required for correct operation.

### Tool Permissions

Allowed tool categories and explicit restrictions. Permissions should be minimal and should distinguish read-only, write, execution, network, notification, memory, state, and audit access.

### Memory Access

Whether the agent can read memory, propose memory updates, or must not access memory. Memory access must be justified by responsibility.

### State Access

Whether the agent receives state snapshots, requests state transitions through the orchestrator, or writes only through the State Management Agent.

### Failure Behavior

Known failure modes and the artifact or status the agent returns for each mode.

### Retry Policy

Whether the agent may be retried, what must change between retries, and what signals should route to Retry & Recovery.

### Confidence Reporting

The expected confidence scale, minimum evidence required for high confidence, and how uncertainty must be expressed.

### Audit Requirements

Events, decisions, tool invocations, side effects, and evidence references that must be emitted for audit logging.

## Contract Template

```yaml
identity:
  name: Example Agent
  version: contract version or implementation version

purpose: >
  One sentence explaining the agent's reason to exist.

responsibilities:
  - Concrete owned responsibility.

non_responsibilities:
  - Work explicitly owned by another agent.

inputs:
  required:
    - artifact or field
  optional:
    - artifact or field
  constraints:
    - scope, budget, policy, or safety limit

outputs:
  artifacts:
    - artifact name
  events:
    - event name
  recommendations:
    - optional next action recommendation

dependencies:
  agents:
    - upstream or downstream agent
  artifacts:
    - required artifact type
  policies:
    - applicable policy

tool_permissions:
  allowed:
    - read-only repository inspection
  denied:
    - repository mutation
    - external notification

memory_access:
  mode: none | read_curated | propose_update
  justification: why memory is or is not needed

state_access:
  mode: none | read_snapshot | request_transition
  restrictions:
    - no direct lifecycle mutation

failure_behavior:
  - condition: known failure condition
    status: failed | partial | blocked | escalated
    output: required failure artifact

retry_policy:
  retryable: true | false
  max_attempts: policy-owned value, not hardcoded here
  requires_changed_input: true
  route_to: Retry & Recovery Agent when needed

confidence_reporting:
  scale: high | medium | low
  high_requires:
    - direct evidence or successful command
  must_include:
    - assumptions
    - gaps
    - evidence references

audit_requirements:
  events:
    - material decision
    - tool invocation
  evidence_refs_required: true
  secret_handling: redact sensitive values
```

## Message Contract

Agent messages should use a stable envelope:

```yaml
message_id: unique message id
correlation_id: issue workflow id
sender: agent identity
recipient: agent identity
message_type: request | response | event | escalation | audit
intent: requested outcome
inputs: artifact refs or bounded inline data
constraints: relevant limits and policies
required_output: artifact type and acceptance requirements
confidence_required: threshold when applicable
trace_refs: related state, audit, memory, or tool references
created_at: timestamp
```

Responses should include:

```yaml
status: success | partial | failed | blocked | escalated
outputs: artifact refs or bounded inline data
evidence: paths, lines, commands, issue refs, or reasoning summary
confidence: high | medium | low
risks: assumptions, gaps, hazards
next_recommended_action: optional
audit_events: audit-worthy facts
```

## Artifact Contract

Artifacts should be:

- Named by type and workflow correlation id.
- Versioned or timestamped.
- Linked to producing agent.
- Linked to source evidence.
- Small enough to be passed safely, or stored with a reference.
- Immutable after publication; revisions create new artifact versions.

## Contract Review Checklist

Before accepting a new or changed agent contract:

- Does the agent own a unique responsibility?
- Are non-responsibilities clear?
- Are inputs and outputs artifact-based?
- Are tool permissions minimal?
- Is state mutation centralized?
- Is memory access justified?
- Are failure modes explicit?
- Does retry require changed evidence or strategy?
- Is confidence tied to evidence?
- Can audit reconstruct what happened?
