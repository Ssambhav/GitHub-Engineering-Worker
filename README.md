# GitHub Engineering Worker

GitHub Engineering Worker is an autonomous AI engineering platform built on OpenClaw. It receives a GitHub repository and a GitHub Issue, then coordinates specialized agents to understand the issue, gather repository context, identify root cause, plan a fix, apply approved changes, validate the result, recover from failures, escalate when necessary, and produce a professional engineering review.

This repository currently defines the platform foundation and architecture. It intentionally does not implement business logic, tools, workflows, retries, memory, or runtime state execution.

## Architecture

The system is designed as a multi-agent engineering organization rather than one giant prompt.

Core documents:

- [AGENTS.md](AGENTS.md): canonical agent architecture and contracts.
- [WORKFLOW.md](WORKFLOW.md): canonical workflow engine and orchestration architecture.
- [STATES.md](STATES.md): canonical execution state machine architecture.
- [Architecture Overview](docs/architecture.md): system layers, lifecycle, autonomy boundaries, and extensibility model.
- [Agent Reference](docs/agents.md): quick reference for required agents and responsibility boundaries.
- [Agent Contract Specification](docs/specifications/agent-contract.md): reusable contract shape for production agents.
- [Agent Communication Specification](docs/specifications/agent-communication.md): message, event, shared context, and synchronization model.
- [Retry & Recovery System](retry/README.md): resilience layer, failure taxonomy, retry policies, recovery contracts, and escalation rules.

## Design Principles

- Separate lifecycle coordination from engineering execution.
- Give each agent a clearly bounded responsibility.
- Communicate through artifacts, structured messages, and events.
- Centralize state ownership and audit logging.
- Use evidence-backed confidence reporting.
- Make workflow transitions deterministic, explainable, and auditable.
- Escalate when autonomy would be unsafe.
- Keep architecture declarative until implementation work is explicitly scoped.

## Repository Areas

- `agents/`: agent domain folders and future implementation locations.
- `docs/`: architecture, specifications, and operator documentation.
- `configuration/`: declarative settings and future environment configuration.
- `memory/`: memory documentation and future memory stores.
- `states/`: execution state machine contracts, definitions, transition graph, events, validators, and future state stores.
- `audit/`: audit documentation and future audit evidence.
- `retry/`: retry and recovery policies, contracts, strategy templates, history records, reports, and future retry queues.
- `review/`: review documentation and future review artifacts.
- `tools/`: tool integration documentation and future tool adapters.
- `workflows/`: workflow documentation and future workflow definitions.
- `runtime/`: runtime artifact, cache, sandbox, and temporary areas.

## Status

Foundation and architecture documentation are the current focus. Contributors should preserve the declarative boundary: do not add stub implementation code or hardcoded prompts when updating architecture documents.
