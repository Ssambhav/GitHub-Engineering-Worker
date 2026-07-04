# Workflows Directory

This directory is reserved for future declarative workflow definitions and workflow-specific documentation.

The authoritative Workflow Engine architecture is [../WORKFLOW.md](../WORKFLOW.md). Reusable workflow contracts are defined in [../docs/specifications/workflow-contract.md](../docs/specifications/workflow-contract.md).

## Current Boundary

This repository currently defines workflow architecture only. Do not add runtime orchestration code, executable state machines, hardcoded prompts, retry logic, memory logic, or business logic unless that work is explicitly scoped separately.

## Expected Future Structure

Future workflow directories should contain declarative definitions and documentation aligned with the workflow contract:

- trigger and inputs
- legal stages and transitions
- participating agents
- required tool capabilities
- events emitted and consumed
- checkpoints
- terminal states
- audit requirements
- extension points

Workflow implementations must remain separate from architecture documentation.
