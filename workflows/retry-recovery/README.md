# Retry Recovery Workflow

The Retry Recovery Workflow is the workflow-level view of the Retry & Recovery System. It routes failed stages to failure classification, recovery planning, changed retry execution, validation, escalation, or terminal failure.

Canonical subsystem documentation lives in [../../retry/README.md](../../retry/README.md).

## Workflow Boundary

This folder documents workflow composition only. Runtime retry logic, queue processing, tool execution, agent implementation, and business behavior are intentionally out of scope.

## Required Artifacts

- failure analysis;
- recovery plan;
- retry attempt record;
- retry outcome;
- escalation report when recovery is unsafe or exhausted.

## Required Events

- `FailureClassified`
- `RecoveryPlanned`
- `RetryStarted`
- `RetryCompleted`
- `RetryEscalated`

## Resume Targets

Recovery may resume at the earliest safe stage that can correct the failure:

- Repository Search
- Read Relevant Files
- Analyze Root Cause
- Create Engineering Plan
- Generate Patch
- Apply Changes
- Validate
- Run Tests

State transitions, checkpoints, and locks remain owned by the State Management Agent.
