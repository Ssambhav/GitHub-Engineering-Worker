# Failure Analysis Engine

The Failure Analysis Engine is a contract for analyzing failed workflow stages. It answers what failed, why it failed, whether recovery is safe, and what must change before retry.

This directory does not implement analysis logic.

## Required Questions

- What failed?
- Where did it fail?
- Why did it fail?
- What side effects occurred?
- Can it be recovered?
- Is retry safe?
- Should more context be gathered?
- Should another tool be selected?
- Should another agent be used?
- Should the prompt be improved?
- Should the patch or plan change?
- Should confidence decrease?
- Should execution stop?
- Should escalation occur?

## Required Inputs

- failure event or tool failure response;
- current workflow state snapshot;
- current stage and legal transitions;
- retry history;
- involved agent/tool ids;
- relevant artifact refs;
- side effect refs;
- confidence snapshot;
- applicable policies.

## Required Output

The output is a Failure Analysis artifact conforming to [../contracts/failure-analysis.contract.yaml](../contracts/failure-analysis.contract.yaml).

## Analysis Rules

- Unknown failures are critical until classified.
- Side effects must be identified before retry eligibility is granted.
- A retry recommendation must name the invalid assumption or missing evidence.
- Repeated failures must be compared against retry history.
- Confidence changes must be explicit and scoped.
- Escalation must include the smallest human/operator decision needed.
