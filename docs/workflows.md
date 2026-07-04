# Workflow Engine Overview

GitHub Engineering Worker uses a workflow engine to coordinate agents, tools, state, events, checkpoints, retries, validation, escalation, and review for autonomous GitHub Issue work.

The canonical workflow architecture is [WORKFLOW.md](../WORKFLOW.md).

## Responsibilities

The workflow engine determines:

- Execution order.
- State transitions.
- Branching.
- Decision points.
- Retry routing.
- Recovery planning.
- Validation checkpoints.
- Escalation.
- Safe termination.

The engine coordinates; it does not perform agent work or execute tools directly.

## Primary Workflow

The primary issue workflow is:

```text
Receive Repository
Receive Issue
  -> Understand Issue
  -> Collect Context
  -> Repository Search
  -> Read Relevant Files
  -> Analyze Root Cause
  -> Create Engineering Plan
  -> Generate Patch
  -> Apply Changes
  -> Validate
  -> Run Tests
  -> Decision Point
      -> Retry
      -> Escalate
      -> Review
  -> Completed
```

Each transition is gated by state, artifacts, confidence, policy, and auditability.

## Key Specifications

- [Workflow Contract](specifications/workflow-contract.md): reusable workflow, stage, decision, event, checkpoint, and branch contracts.
- [Agent Contract](specifications/agent-contract.md): agent boundaries used by workflow stages.
- [Agent Communication](specifications/agent-communication.md): event and artifact communication model.
- [Tool Contract](specifications/tool-contract.md): tool capabilities used by workflow stages.
- [Tool Invocation](specifications/tool-invocation.md): controlled tool execution model.
- [Retry & Recovery System](../retry/README.md): retry policies, failure analysis, recovery plans, history, and escalation contracts.

## Documentation Boundary

Workflow documents are declarative. They should not include runtime implementation code, hardcoded prompts, executable state machines, retry algorithms, or business logic.

Future workflow definitions should reference stage contracts, events, tool capabilities, agents, and policy-owned thresholds rather than embedding execution code.
