# Agent Reference

This document is the quick reference for agents in GitHub Engineering Worker. The full contract for every agent is [AGENTS.md](../AGENTS.md).

## Agent Organization

The system separates lifecycle ownership from engineering work:

- Engineering Orchestrator Agent owns coordination and decisions.
- Specialist agents produce bounded artifacts.
- State Management Agent owns durable workflow state.
- Audit Logging Agent owns event and decision history.
- Memory Management Agent owns reusable learning.

No specialist agent should both make a global lifecycle decision and execute the resulting work.

## Required Agents

| Agent | Primary artifact | Responsibility boundary |
| --- | --- | --- |
| Engineering Orchestrator | Lifecycle decision | Coordinates agents and gates transitions; does not do engineering work. |
| Issue Understanding | Issue brief | Turns raw issue content into intent, constraints, and acceptance criteria. |
| Repository Context | Repository context summary | Maps project structure, conventions, and validation entry points. |
| Repository Search | Ranked search results | Finds likely files, symbols, tests, and docs. |
| File Reader | File excerpt bundle | Reads only requested files or line ranges and summarizes evidence. |
| Root Cause Analysis | Root cause report | Explains the failure mechanism and minimal behavioral change. |
| Planning | Implementation plan | Defines change steps, validation strategy, and risk. |
| Patch Generation | Patch proposal | Designs exact intended changes without applying them. |
| Code Modification | Applied change manifest | Applies approved edits and reports the resulting diff. |
| Validation | Validation report | Judges whether the change satisfies criteria and quality expectations. |
| Test Execution | Test execution report | Runs approved commands and reports factual results. |
| Retry & Recovery | Recovery recommendation | Diagnoses failures and proposes a changed strategy or escalation. |
| Review Generation | Final engineering review | Produces maintainer-facing summary and evidence. |
| Escalation | Escalation packet | Frames human decisions when autonomy is unsafe. |
| Audit Logging | Audit trail | Records decisions, events, tool refs, and side effects. |
| Memory Management | Memory context/update proposal | Retrieves and curates reusable learning. |
| State Management | State snapshot/checkpoint | Owns locks, phase, retries, suspension, and terminal state. |

## Confidence Model

Every agent response must include confidence and justification. Confidence should be tied to evidence quality, not verbosity.

Recommended categories:

- High: direct evidence supports the conclusion and expected downstream action is clear.
- Medium: evidence is plausible but incomplete or partially indirect.
- Low: conclusion is speculative, blocked by missing context, or requires human judgment.

The orchestrator decides whether confidence is sufficient for the next phase.

## Tool Permission Model

Agents receive only the tool categories required by their contract:

- Read-only agents may inspect issues, repository metadata, files, docs, logs, or previous artifacts.
- Planning agents may inspect but not mutate code.
- Code Modification may edit only approved files.
- Test Execution may run only approved commands.
- Audit, Memory, and State agents interact with their respective stores.
- Escalation may notify humans only when authorized by policy.

Tool permissions should be narrower than repository permissions whenever possible.

## Memory Access Model

Memory access is not universal:

- Orchestrator may request relevant memory summaries.
- Planning and Retry & Recovery may receive curated prior lessons.
- Review Generation may receive terminal workflow summaries.
- Specialist agents should not browse memory unless their contract requires it.

Memory must not replace repository evidence.

## State Access Model

State writes are centralized through State Management. Other agents may receive state snapshots but must not mutate lifecycle phase, retry count, locks, or terminal status directly.

## Audit Requirements

All agents must emit audit-worthy information for:

- Material conclusions.
- Confidence changes that alter workflow direction.
- Tool invocations.
- File modifications.
- Test executions.
- Retry decisions.
- Escalation decisions.
- Terminal outcomes.

Audit entries should reference artifacts and evidence rather than copying unnecessary content.

## Extension Rules

Before adding an agent, confirm that the responsibility is not already owned. New agents must define:

- Identity
- Purpose
- Responsibilities
- Inputs
- Outputs
- Dependencies
- Tool permissions
- Memory access
- State access
- Failure behavior
- Retry policy
- Confidence reporting
- Audit requirements

New agents must produce artifacts for the orchestrator. They must not silently perform lifecycle transitions.
