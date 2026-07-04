# Retry Reports

Reports provide human-readable and machine-referenceable summaries of recovery decisions. They should be concise, evidence-backed, and safe to share with maintainers or operators according to sensitivity policy.

## Report Types

- Recovery report: explains a retry plan and changed strategy.
- Escalation report: explains why autonomous recovery stopped.
- Terminal retry report: summarizes retry history and final outcome.

## Escalation Report Requirements

An escalation report must include:

- workflow and issue refs;
- failed stage;
- failure type and severity;
- retry attempts and strategies;
- why autonomous recovery is unsafe or exhausted;
- repository safety status;
- validation/test status;
- smallest human or operator decision needed;
- recommended options;
- evidence refs;
- audit refs.
