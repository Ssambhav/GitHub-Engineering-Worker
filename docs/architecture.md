# Architecture Overview

GitHub Engineering Worker is a production-grade autonomous engineering platform built on OpenClaw. It receives a GitHub repository and a GitHub Issue, then coordinates specialized agents to understand, modify, validate, recover, and report on the work.

The canonical agent contract is [AGENTS.md](../AGENTS.md). This document explains the architectural shape around that contract.

## System Layers

### Orchestration Layer

The Engineering Orchestrator owns lifecycle control. It selects agents, evaluates confidence, gates phase transitions, manages retries, and terminates safely. It never performs repository analysis, patch design, code editing, or validation itself.

### Specialist Agent Layer

Specialist agents own bounded responsibilities such as issue understanding, repository search, root cause analysis, patch generation, test execution, and review generation. They produce structured artifacts and confidence reports for the orchestrator.

### Artifact Layer

Artifacts are the primary communication unit:

- Issue brief
- Repository context summary
- Ranked search results
- File excerpt bundle
- Root cause report
- Implementation plan
- Patch proposal
- Applied change manifest
- Validation report
- Test execution report
- Retry report
- Escalation packet
- Final engineering review

Artifacts should be durable, auditable, and referential. Agents should pass artifact references rather than duplicating large content.

### State Layer

The State Management Agent owns workflow state, locks, checkpoints, retries, suspension, resumption, and terminal status. Specialist agents may read authorized state snapshots but do not mutate lifecycle state directly.

### Observability Layer

The Audit Logging Agent records material decisions, events, tool invocations, evidence references, and terminal outcomes. Audit records must be sufficient to reconstruct the issue lifecycle without exposing secrets.

### Memory Layer

The Memory Management Agent retrieves relevant prior knowledge and proposes durable learning after a workflow. Memory is for reusable patterns, not raw per-run logs or hidden state.

### Retry & Recovery Layer

The Retry & Recovery System classifies failures, plans changed recovery attempts, prevents identical retries, tracks retry history, recalculates confidence, and routes unsafe cases to escalation. It is policy- and artifact-driven; it does not execute tools, modify files, or own workflow state.

### Tool Layer

Tools are invoked only through authorized agent contracts. Architecture documents define which categories of tools an agent may use; they do not implement tools or workflow logic.

## Lifecycle Flow

1. Intake repository and issue reference.
2. Initialize state, audit trail, and memory lookup.
3. Produce issue brief and acceptance criteria.
4. Build repository context.
5. Search for relevant files, symbols, tests, and docs.
6. Read only necessary files or excerpts.
7. Analyze root cause.
8. Produce implementation and validation plan.
9. Generate patch proposal.
10. Apply approved changes.
11. Validate diff and run tests.
12. Recover from failures with changed strategy, or escalate.
13. Generate final engineering review.
14. Close state and audit trail.

## Autonomy Boundaries

The worker may autonomously read repository content, analyze code, propose plans, apply approved internal modifications, and run approved validation commands.

The worker must escalate when:

- Issue intent is ambiguous and cannot be inferred safely.
- Product behavior requires a human decision.
- Repository or tool access is unavailable.
- State, auditability, or lock integrity cannot be guaranteed.
- Validation cannot establish acceptable safety.
- Retry budget is exhausted or failures repeat without a new hypothesis.

## Scalability Model

The architecture scales by adding specialist agents and artifact types rather than expanding the orchestrator into a monolith. Multiple issue workflows may run concurrently when state locks prevent conflicting repository writes. Read-only agents can operate in parallel when their inputs are independent and their outputs are reconciled by the orchestrator.

## Maintainability Model

Maintainability depends on stable contracts:

- Agent inputs and outputs are explicit.
- Tool permissions are narrow.
- State writes are centralized.
- Audit events are normalized.
- Memory is curated separately from logs.
- Retry behavior is documented, bounded, evidence-backed, and forbidden from repeating identical attempts.

## Extensibility Model

Add new agents when a new capability has a distinct responsibility, artifact, and confidence model. Examples include Security Analysis, Dependency Upgrade Analysis, Performance Profiling, API Compatibility Review, Database Migration Review, and Documentation Review.

Do not add an agent only to split a prompt mechanically. A new agent must reduce coupling, improve auditability, or isolate a specialized tool/risk domain.
