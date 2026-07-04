# Documentation

This directory contains project documentation for GitHub Engineering Worker, an autonomous OpenClaw-based platform that owns the lifecycle of a GitHub Issue from intake through validation and review.

## Primary Documents

- [Architecture Overview](architecture.md): system layers, lifecycle flow, autonomy boundaries, scalability, and extensibility.
- [Agent Reference](agents.md): quick reference for all required agents and their boundaries.
- [Tool Framework Overview](tools.md): controlled execution boundary, registry, permissions, invocation, and failure model.
- [Workflow Engine Overview](workflows.md): orchestration lifecycle, stages, decision model, branching, checkpoints, and events.
- [Retry & Recovery System](../retry/README.md): failure taxonomy, retry lifecycle, policies, recovery plans, history, and escalation reports.
- [Canonical State Machine](../STATES.md): execution states, transition graph, persistence, recovery, validation, events, and contracts.
- [Canonical Agent Architecture](../AGENTS.md): complete agent contracts and orchestration model.
- [Canonical Tool Framework](../TOOLS.md): complete tool architecture and contract catalog.
- [Canonical Workflow Engine](../WORKFLOW.md): complete workflow orchestration architecture.
- [Retry Policy](../retry/RETRY_POLICY.md) and [Failure Policy](../retry/FAILURE_POLICY.md): canonical retry and failure recovery rules.
- [Specifications](specifications/README.md): formal contracts for agents, communication, tools, workflows, states, and lifecycle behavior.
- [Operations](operations/README.md): operational runbooks and future operator guidance.
- [Getting Started](getting-started.md): project setup and contributor entry point.

## Documentation Rules

- Architecture documents are declarative.
- Do not implement tools, prompts, workflows, retries, memory, or runtime state execution in documentation.
- Keep responsibilities separated by agent.
- Prefer artifact contracts and evidence references over prose-only coordination.
- Update the canonical AGENTS.md when agent responsibilities or lifecycle rules change.
- Update the canonical TOOLS.md when tool categories, contracts, permissions, or invocation rules change.
- Update the canonical WORKFLOW.md when stages, transitions, decisions, events, or checkpoints change.
- Update the canonical STATES.md when primary states, transition legality, persistence, recovery, validation, or state events change.
