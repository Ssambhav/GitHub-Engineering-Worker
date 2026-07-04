# Agent Communication Specification

GitHub Engineering Worker agents communicate through structured requests, responses, events, and artifact references. Communication must be explicit, auditable, and limited to the information needed for the receiving agent's responsibility.

## Communication Goals

- Keep agents loosely coupled.
- Prevent hidden dependencies on transcript history.
- Minimize context transfer.
- Preserve evidence and decisions.
- Support suspension, resumption, retries, and audit reconstruction.

## Communication Channels

### Request/Response

Use request/response when an agent needs a bounded artifact from another agent.

Examples:

- Orchestrator requests an issue brief from Issue Understanding.
- Orchestrator requests ranked search results from Repository Search.
- Root Cause Analysis requests additional file excerpts through the orchestrator.

Requests must include expected output and constraints. Responses must include status, evidence, confidence, and risks.

### Events

Use events for lifecycle facts and observability. Events are not commands.

Recommended event names:

- issue.accepted
- state.initialized
- issue.understood
- repository.context_collected
- repository.search_completed
- files.read
- root_cause.completed
- plan.proposed
- patch.proposed
- patch.applied
- validation.completed
- tests.completed
- retry.recommended
- escalation.requested
- review.generated
- workflow.completed
- workflow.failed

Events should be immutable and correlated to workflow id.

### Escalations

Use escalation messages when autonomous continuation is unsafe. Escalation messages must contain a specific decision request, not a vague status update.

### Audit Messages

Audit messages record material actions, decisions, and side effects. Audit Logging may receive events from every agent, but agents should avoid duplicating full content already stored in artifacts.

## Message Envelope

```yaml
message_id: stable unique id
correlation_id: workflow id
sender: producing agent
recipient: receiving agent or event stream
message_type: request | response | event | escalation | audit
intent: concise reason for communication
inputs:
  artifacts:
    - artifact reference
  inline:
    - bounded field when necessary
constraints:
  scope: allowed files, directories, commands, or phases
  budget: context, time, or retry limits
  policy: applicable policy references
required_output:
  artifact_type: expected artifact
  acceptance: conditions for a usable response
confidence_required: optional threshold
trace_refs:
  state: state snapshot or checkpoint ref
  audit: related audit event refs
  memory: memory refs if used
created_at: timestamp
```

## Response Envelope

```yaml
status: success | partial | failed | blocked | escalated
outputs:
  artifacts:
    - produced artifact reference
  inline:
    - bounded summary when useful
evidence:
  repository_refs:
    - path and optional line
  issue_refs:
    - issue/comment/link ref
  command_refs:
    - command execution ref
confidence:
  level: high | medium | low
  rationale: evidence-backed explanation
risks:
  - assumption, gap, or hazard
next_recommended_action: optional recommendation to orchestrator
audit_events:
  - audit-worthy fact
```

## Shared Context Rules

Shared context should be artifact-based. Agents should not receive the entire repository, complete logs, or full prior conversation unless their contract requires it.

Preferred context order:

1. Artifact reference.
2. Bounded summary with evidence references.
3. Exact file excerpt.
4. Full file only when necessary.
5. Full repository context only for specialized indexing or context agents.

## Synchronization

The State Management Agent is the synchronization authority.

It owns:

- Current phase.
- Active agent.
- Artifact versions.
- Repository write locks.
- Retry count.
- Suspension checkpoints.
- Terminal status.

The orchestrator requests state transitions. Specialist agents report status and artifacts but do not directly advance lifecycle phase.

## Coordination

The Engineering Orchestrator coordinates all cross-agent work:

- It selects the next agent.
- It provides the minimum required context.
- It evaluates outputs against phase requirements.
- It decides whether to gather more evidence, retry, escalate, or terminate.

Specialist agents may recommend next actions, but recommendations are advisory.

## Avoiding Unnecessary Communication

Agents should avoid communication when:

- Existing artifacts are fresh and sufficient.
- The requested work belongs to another agent and should be routed by the orchestrator.
- The answer would duplicate data already available by artifact reference.
- More detail would not change the orchestrator's decision.

The orchestrator should avoid unnecessary communication by:

- Reusing artifact references.
- Asking targeted questions.
- Setting explicit read and search scopes.
- Stopping context gathering when confidence thresholds are met.
- Rejecting speculative follow-up requests without expected value.

## Conflict Handling

When agent outputs conflict, the orchestrator should:

1. Identify the specific conflicting claims.
2. Compare evidence quality and freshness.
3. Request targeted additional evidence if it can resolve the conflict.
4. Route to Retry & Recovery if conflict follows failed implementation or validation.
5. Escalate if the conflict is product-level or cannot be resolved safely.

## Resumption

On resume, agents must treat previous context as stale until the orchestrator provides current state and artifact versions. The orchestrator verifies repository state, artifact freshness, and lock ownership before continuing.
