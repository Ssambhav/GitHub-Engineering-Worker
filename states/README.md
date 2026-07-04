# State Subsystem

The state subsystem defines the deterministic execution state machine for GitHub Engineering Worker. It owns the declarative contracts for primary states, transition rules, validation expectations, persistence, events, and extension points.

This directory does not contain runtime execution code. It is production-ready scaffolding for future implementation.

## Directory Layout

| Path | Purpose |
| --- | --- |
| `definitions/` | Primary and nested state definitions. |
| `contracts/` | Reusable schemas and contracts for states, transitions, checkpoints, and snapshots. |
| `transitions/` | Legal transition graph and transition rule catalog. |
| `validators/` | Declarative validation rules for integrity, legality, idempotency, and recovery. |
| `events/` | Lifecycle event catalog and payload contracts. |
| `configuration/` | Default policy knobs, timeouts, confidence thresholds, and retry limits by state. |
| `interfaces/` | Service-facing interface contracts for state stores, transition validators, event publishers, and checkpoint managers. |
| `checkpoints/` | Persistent checkpoint storage area when runtime is implemented. |
| `issues/` | Issue-scoped state storage area when runtime is implemented. |
| `locks/` | Lock state storage area when runtime is implemented. |
| `workflows/` | Workflow instance state storage area when runtime is implemented. |

## Canonical Document

The canonical state machine architecture is [../STATES.md](../STATES.md).

## Non-Responsibilities

The state subsystem does not:

- execute workflows.
- invoke agents.
- call tools.
- implement retry logic.
- modify repositories.
- store raw logs as authoritative state.

## Extension Rule

New state capabilities must be added as contracts, definitions, or configuration first. Runtime implementation must be explicitly scoped separately.
