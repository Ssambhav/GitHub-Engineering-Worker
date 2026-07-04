# ADR 0001: Foundation-Only Repository

## Status

Accepted

## Context

The initial project goal is to create a production-ready foundation for an autonomous GitHub Issue engineering worker without implementing business logic.

## Decision

The repository separates agents, tools, workflows, state, memory, policies, logs, runtime, utilities, configuration, documentation, audit, review, and retry concerns. Each area is documented and prepared for future implementation.

## Consequences

- The repository is extensible without committing premature behavior.
- Future implementations must attach to documented boundaries.
- Empty runtime directories are represented by README files instead of placeholder code.
