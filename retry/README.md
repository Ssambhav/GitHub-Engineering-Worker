# Retry & Recovery System

The Retry & Recovery System is the resilience layer for GitHub Engineering Worker. It turns failed attempts into better-informed engineering attempts instead of blindly repeating failed work.

This subsystem is declarative only. It defines failure categories, retry contracts, recovery policies, history records, analysis reports, and extension points. It does not implement runtime retry logic, agents, tools, patching, validation, or business behavior.

## Philosophy

Retries are not repetitions.

Every retry must introduce at least one material improvement:

- new repository, issue, tool, state, memory, or validation evidence;
- narrowed or corrected scope;
- changed root-cause hypothesis;
- changed tool, agent, prompt, patch, or validation strategy;
- restored repository state or safer checkpoint;
- clearer confidence calculation or escalation rationale.

The worker must never perform an identical retry, hide a failure, bypass validation, modify unrelated files, or continue when repository safety is uncertain.

## Responsibilities

The Retry & Recovery System defines how the orchestrator and Retry & Recovery Agent should:

- classify failures consistently;
- decide whether recovery is safe;
- require changed retry strategies;
- track attempt history;
- prevent infinite loops and duplicate fixes;
- select safe resume stages;
- preserve auditability and repository recoverability;
- escalate when autonomous continuation is unsafe.

## Non-Responsibilities

This subsystem does not:

- run commands;
- execute tools;
- implement agents;
- generate or apply patches;
- mutate workflow state directly;
- store long-term memory directly;
- decide product behavior.

Runtime code must implement these contracts through the Workflow Engine, State Machine, Memory System, Tool Framework, and Audit Logging System.

## Repository Layout

- [policies/](policies/README.md): retry policy precedence, budgets, and escalation rules.
- [strategies/](strategies/README.md): declarative recovery strategy catalog and reusable strategy shapes.
- [analyzers/](analyzers/README.md): failure analysis questions, inputs, and required outputs.
- [history/](history/README.md): retry attempt history and anti-repetition records.
- [contracts/](contracts/README.md): reusable YAML contracts for failures, plans, strategies, and outcomes.
- [configuration/](configuration/README.md): policy templates and configuration defaults.
- [interfaces/](interfaces/README.md): service interface contracts future runtime code may implement.
- [reports/](reports/README.md): escalation, recovery, and completion report templates.
- [queues/](queues/README.md): reserved retry queue documentation.
- [dead-letter/](dead-letter/README.md): unrecoverable failure and terminal handoff documentation.

## Integration Points

- [AGENTS.md](../AGENTS.md): defines Retry & Recovery Agent responsibilities.
- [WORKFLOW.md](../WORKFLOW.md): defines retry lifecycle stage, branching, checkpoints, and events.
- [STATES.md](../STATES.md): owns retry state, locks, checkpoints, terminal status, and corruption handling.
- [TOOLS.md](../TOOLS.md): owns tool invocation, tool failure contracts, and tool retry metadata.
- [memory/](../memory/README.md): stores reusable lessons and retry history references under memory policy.
- [audit/](../audit/README.md): records material failure, recovery, retry, and escalation events.

## Core Artifacts

Retry workflows exchange these artifacts by reference:

- failure analysis;
- recovery plan;
- retry strategy;
- retry attempt record;
- validation evidence;
- anti-repetition comparison;
- confidence recalculation;
- escalation report;
- terminal retry outcome.

Large logs, patches, tool outputs, and test output must be referenced by artifact id, not copied into retry reports.

## Safety Invariants

- A retry must have a changed strategy before execution.
- The retry target stage must be the earliest safe stage that can correct the failure.
- Repository write retries require a known base revision, approved scope, and safe cleanup or restore plan.
- Validation failures may only retry through changed patch, plan, root-cause, or evidence strategy.
- Unknown or critical failures may receive at most one diagnostic recovery attempt when side effects are known safe.
- Repeated identical failures escalate.
- Exhausted retry budgets escalate.
- Irrecoverable state corruption fails or escalates immediately.

## Extension Guide

To add a new retry strategy or failure category:

1. Add or update the taxonomy in [FAILURE_POLICY.md](FAILURE_POLICY.md).
2. Add a strategy definition under [strategies/](strategies/).
3. Update policy eligibility in [policies/](policies/).
4. Add or revise the relevant contract in [contracts/](contracts/).
5. Add report fields if operators need new evidence.
6. Cross-reference workflow, state, memory, audit, or tool contracts when ownership changes.
7. Do not add runtime behavior in this directory.
