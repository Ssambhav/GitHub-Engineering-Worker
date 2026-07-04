# Workflow Contract Specification

Workflow contracts define how GitHub Engineering Worker coordinates agents, tools, state, memory, policy, validation, retries, escalation, and review. Contracts are declarative and must not contain runtime implementation code.

The canonical Workflow Engine architecture is [WORKFLOW.md](../../WORKFLOW.md).

## Workflow Contract

Every workflow must define:

```yaml
workflow_id: stable identifier
name: human-readable name
purpose: workflow objective
trigger:
  type: issue_assigned | manual | scheduled | event | child_workflow
  required_inputs:
    - repository ref
    - issue ref
terminal_states:
  - Completed
  - Escalated
  - Failed
  - Cancelled
stages:
  - stage ids in legal graph
events:
  - events emitted or consumed
agents:
  - participating agent ids
tool_capabilities:
  - required tool categories or capabilities
state_requirements:
  - checkpoints, locks, artifacts, context fields
confidence_model:
  - fields and thresholds
retry_policy:
  - policy references, not embedded logic
audit_requirements:
  - required events and decision records
extension_points:
  - supported stage or branch insertions
```

## Stage Contract

Every stage must define:

```yaml
stage_id: stable identifier
purpose: why this stage exists
entry_conditions:
  - required state, artifacts, permissions, confidence, or locks
inputs:
  - artifact refs or context fields
agents_involved:
  - agent ids
allowed_tools:
  - tool categories or capability ids
execution_rules:
  - deterministic constraints
outputs:
  - artifact refs, state updates, or events
exit_conditions:
  success:
    - objective criteria to advance
  failure:
    - objective criteria to branch
confidence_updates:
  - confidence fields affected
next_possible_states:
  - stage ids or terminal states
audit_requirements:
  - required events, evidence, decisions, and side effects
```

## Decision Contract

Every decision point must define:

```yaml
decision_id: stable identifier
inputs:
  - state fields, artifact refs, confidence fields, failure refs
criteria:
  - objective rule
possible_outcomes:
  - next stage or terminal state
required_reason:
  - evidence or policy reference
audit_requirements:
  - decision record fields
```

Decision criteria must be objective enough that the same state and artifacts produce the same outcome.

## Event Contract

Every workflow event must define:

```yaml
event_name: stable name
publisher: agent, tool, orchestrator, or state manager
subscribers:
  - consumers
payload:
  required:
    - field
  optional:
    - field
audit_level: none | metadata | full | security_sensitive
state_effect: none | checkpoint | transition | terminal
```

Events are immutable facts. Commands and requests should not be modeled as events.

## Checkpoint Contract

Every checkpoint must persist:

- Workflow id.
- Current stage.
- Repository revision and workspace reference.
- Artifact refs and versions.
- Confidence snapshot.
- Retry count and failure refs.
- Locks held or released.
- Tool invocation refs.
- Audit refs.
- Cleanup obligations.

## Branch Contract

Every branch must define:

- Trigger condition.
- Failure or decision category.
- Resume stage or terminal state.
- Required artifacts.
- Retry eligibility.
- Escalation criteria.
- Audit requirements.

## Contract Quality Checklist

- Are all stages contract-defined?
- Are entry and exit conditions objective?
- Are transitions legal and auditable?
- Are confidence updates explicit?
- Are allowed agents and tools scoped?
- Are checkpoints sufficient for restart?
- Are retry branches changed-strategy aware?
- Are terminal states safe and summarized?
- Are extension points declared without embedding implementation logic?
