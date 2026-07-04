# Retry Policies

Retry policies are declarative controls used by the orchestrator, Retry & Recovery Agent, State Management Agent, Tool Framework, and Validation Agent. They define eligibility, budgets, precedence, safety gates, and escalation triggers.

Canonical policy narrative: [../RETRY_POLICY.md](../RETRY_POLICY.md).

## Policy Stack

1. Global Retry Policy
2. Workflow Retry Policy
3. Agent Retry Policy
4. Tool Retry Policy
5. Patch Retry Policy
6. Validation Retry Policy
7. Testing Retry Policy
8. Escalation Policy

Stricter policy wins. Repository safety, state integrity, permissions, and human approval requirements always override retry eligibility.

## Required Policy Fields

```yaml
policy_id: retry.global.default
policy_version: 1.0.0
owner: Retry & Recovery System
scope:
  workflow_types:
    - issue_lifecycle
  stages:
    - any
limits:
  max_total_retries: 3
  max_same_failure_retries: 1
  max_unknown_failure_diagnostics: 1
eligibility:
  requires_changed_strategy: true
  requires_known_side_effects: true
  requires_auditability: true
  requires_state_integrity: true
escalation:
  on_budget_exhausted: true
  on_repeated_identical_failure: true
  on_repository_safety_risk: true
  on_human_approval_required: true
audit:
  record_policy_decision: true
  record_retry_budget: true
```

## Policy Decisions

Every retry policy evaluation should produce a decision artifact:

```yaml
decision: eligible | ineligible | escalate | terminal_failure
matched_policies:
  - policy_id
reason:
  summary: string
  evidence_refs:
    - artifact_ref
remaining_budget:
  total: integer
  same_failure: integer
required_changes:
  - changed input, tool, agent, prompt, patch, context, validation, or checkpoint
```

## Extension Rules

- Add new policy files as templates, not executable code.
- Policies must declare owner, scope, precedence, limits, and audit requirements.
- Policies may reference external systems only by contract or artifact ref.
- Policy updates must preserve the no-identical-retry invariant.
