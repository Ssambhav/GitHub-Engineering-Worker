# Retry Contracts

Contracts in this directory define reusable artifact shapes for retry and recovery. They are schemas/templates for future runtime implementations and documentation consumers.

## Contract Catalog

- [failure-analysis.contract.yaml](failure-analysis.contract.yaml): why a failure happened and whether recovery is safe.
- [recovery-plan.contract.yaml](recovery-plan.contract.yaml): what must change before retry.
- [retry-strategy.contract.yaml](retry-strategy.contract.yaml): reusable strategy definition.
- [retry-outcome.contract.yaml](retry-outcome.contract.yaml): terminal or intermediate retry result.

## Contract Rules

- Contracts are artifact-oriented and implementation-neutral.
- Large content is referenced, not embedded.
- Every contract includes owner, version, evidence, confidence, and audit fields.
- Contracts must be usable by workers beyond GitHub Engineering Worker.
