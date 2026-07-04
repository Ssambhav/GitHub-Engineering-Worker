# State Machine Contract Specification

The state machine contract defines how GitHub Engineering Worker represents and validates the lifecycle position of each workflow execution. The canonical architecture is [STATES.md](../../STATES.md).

This specification is declarative only. It does not implement runtime execution, agents, tools, retry logic, or workflow behavior.

## Execution State Contract

Every state must define:

```yaml
state_id: stable UPPER_SNAKE_CASE identifier
category: intake | repository | evidence | reasoning | planning | modification | validation | recovery | review | terminal
terminal: true | false
purpose: why the state exists
owner:
  semantic_owner: agent or subsystem responsible for state meaning
  transition_owner: subsystem allowed to commit transitions
  audit_owner: subsystem responsible for audit records
entry_conditions:
  - objective condition
exit_conditions:
  - objective condition
allowed_operations:
  - bounded operation
allowed_agents:
  - agent id or role
allowed_tools:
  - tool category or capability
required_memory:
  - memory object family or ref type
generated_events:
  - lifecycle event
failure_conditions:
  - failure criterion
recovery_strategy:
  - route or action
confidence_impact:
  fields:
    - confidence field
  update_rule: evidence-backed update rule
audit_requirements:
  - required audit record
timeout_expectations:
  class: short | medium | long | policy-owned
retry_eligibility:
  eligible: true | false
  conditions:
    - condition
success_criteria:
  - objective criterion
next_valid_states:
  - state_id
invalid_transitions:
  - invalid edge or class
```

## Transition Contract

Every transition attempt must define:

```yaml
transition_id: unique idempotency key
workflow_id: workflow instance id
from_state: persisted current state
to_state: requested target state
trigger: event | decision | external_request | policy | recovery | administrative
initiator: actor requesting transition
validator: actor validating transition
reason: bounded reason
preconditions:
  - objective check
postconditions:
  - persisted result
memory_updates:
  - create | update | pin | invalidate | none
confidence_updates:
  - field, prior value, new value, evidence ref
audit_entries:
  - audit record requirement
event_publication:
  - event to publish
failure_handling:
  on_rejected: behavior
  on_partial: behavior
  on_corrupt: behavior
rollback_requirements:
  - cleanup obligation or none
```

## State Snapshot Contract

A persisted state snapshot must include:

- workflow id and state version.
- current primary state and optional nested state.
- repository ref, workspace ref, and revision.
- issue ref.
- artifact refs and versions.
- pinned memory refs.
- confidence snapshot.
- retry metadata.
- lock refs.
- latest checkpoint ref.
- transition history refs.
- audit refs.
- terminal summary ref when terminal.

## Validation Requirements

Validation must check:

- exactly one primary state is active.
- state id belongs to the catalog version.
- transition edge is legal.
- required artifacts, memory refs, locks, permissions, and audit sinks exist.
- confidence gates are satisfied or recovery/escalation is selected.
- terminal states are immutable.
- duplicate transition ids are idempotent or rejected.
- state, checkpoint, audit, and memory refs are mutually consistent.

## Event Requirements

State lifecycle events must be immutable and include:

- event id.
- event name.
- workflow id.
- publisher.
- timestamp.
- payload.
- audit level.
- state effect.

Required lifecycle events are defined in [states/events/lifecycle-events.yaml](../../states/events/lifecycle-events.yaml).

## Extension Requirements

New states must:

- use the state contract.
- be added to the transition graph.
- define validation and audit requirements.
- declare persistence and checkpoint behavior.
- preserve deterministic transition criteria.
- avoid runtime code and business logic.
