# Retry & Recovery Specification

The Retry & Recovery Specification defines the contract surface for recovering from failed autonomous engineering work. It is generic enough for future autonomous workers, while GitHub Engineering Worker is the first target worker.

Canonical subsystem documentation lives in [../../retry/README.md](../../retry/README.md).

## Scope

This specification covers:

- failure classification;
- failure analysis artifacts;
- recovery plan artifacts;
- retry strategy contracts;
- retry history records;
- escalation reports;
- policy precedence;
- safety invariants.

It does not implement retry algorithms, agent behavior, tool execution, repository modification, validation commands, queues, or state persistence.

## Required Artifact Contracts

- [Failure Analysis](../../retry/contracts/failure-analysis.contract.yaml)
- [Recovery Plan](../../retry/contracts/recovery-plan.contract.yaml)
- [Retry Strategy](../../retry/contracts/retry-strategy.contract.yaml)
- [Retry Outcome](../../retry/contracts/retry-outcome.contract.yaml)
- [Retry Attempt Record](../../retry/history/retry-attempt-record.template.yaml)

## Required Policies

- [Retry Policy](../../retry/RETRY_POLICY.md)
- [Failure Policy](../../retry/FAILURE_POLICY.md)
- [Global Retry Policy Template](../../retry/policies/global-retry-policy.template.yaml)

## Required Decisions

Every retry decision must answer:

- Is the failure classified?
- Are side effects known?
- Is repository state safe?
- Is retry policy budget available?
- What changed compared with previous attempts?
- Which stage is the earliest safe resume point?
- What validation proves the retry worked?
- Should confidence decrease, increase, remain unchanged, or become blocked?
- Is escalation required?

## Generic Worker Compatibility

Retry contracts avoid GitHub-specific assumptions except where repository issue workflows reference them. Future workers may replace repository-specific fields with their own task, environment, artifact, and validation refs while preserving:

- failure taxonomy;
- changed-strategy requirement;
- anti-repetition history;
- confidence recalculation;
- side-effect tracking;
- escalation rules;
- audit requirements.

## Safety Requirements

- No identical retry may execute.
- No retry may proceed with unknown unsafe side effects.
- No retry may bypass validation requirements.
- No retry may mutate state or repository content outside the owning subsystem.
- No retry may continue after policy exhaustion.
- Unknown failures must escalate after the allowed diagnostic budget.
