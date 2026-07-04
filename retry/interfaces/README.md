# Retry Interfaces

Interfaces describe future service boundaries for runtime implementations. They are contracts only.

## Interface Catalog

- [retry-coordinator.interface.yaml](retry-coordinator.interface.yaml): evaluates retry eligibility and coordinates recovery artifacts.
- [failure-analyzer.interface.yaml](failure-analyzer.interface.yaml): produces failure analysis artifacts.
- [retry-history-store.interface.yaml](retry-history-store.interface.yaml): reads and writes retry attempt records.

## Boundary Rules

- Interfaces must not own workflow state; State Management does.
- Interfaces must not execute tools; Tool Framework does.
- Interfaces must not mutate files; Code Modification does.
- Interfaces must not store durable learning directly; Memory Management does.
- Interfaces may return artifact refs, policy decisions, and recommendations.
