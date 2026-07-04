# Issue Lifecycle Specification

This specification defines the intended lifecycle boundary for the GitHub Engineering Worker.

## Lifecycle Phases

1. Intake
2. Triage
3. Planning
4. Implementation
5. Verification
6. Pull request preparation
7. Review response
8. Merge readiness
9. Release verification
10. Issue closure

## Foundation Status

This repository defines the architecture only. No phase contains executable business logic yet.

## Required Properties

- Every phase must be auditable.
- Every external action must be attributable.
- Every retry must preserve prior failure context.
- Every human approval gate must be explicit.
- Every issue must have resumable state.
