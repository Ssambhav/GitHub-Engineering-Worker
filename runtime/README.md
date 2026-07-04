# Runtime

This directory contains the Python runtime core and runtime-owned storage areas for GitHub Engineering Worker.

## Python Package

- `execution/`: runtime composition root.
- `orchestrator/`: Engineering Orchestrator implementation.
- `context/`: immutable execution context and builder.
- `events/`: internal event bus.
- `sessions/`: execution session manager.
- `dispatcher/`: registered agent dispatcher.
- `scheduler/`: execution scheduler.
- `configuration/`: typed runtime configuration provider.
- `registry/`: agent, tool, and workflow registries.
- `lifecycle/`: initialization and shutdown management.
- `exceptions/`: runtime exception hierarchy.
- `interfaces/`: reusable runtime protocols.
- `models/`: typed runtime value objects.

## Runtime Storage

- `artifacts/`: generated runtime artifacts.
- `cache/`: runtime cache files.
- `sandbox/`: isolated execution scratch space.
- `tmp/`: temporary files.

The runtime core coordinates execution only. It does not implement GitHub APIs, engineering agents, tools, repository analysis, patch generation, or issue solving.
