# Retry Policy

The Retry Policy defines how recovery attempts are planned, limited, validated, and escalated. It complements the workflow Retry stage in [WORKFLOW.md](../WORKFLOW.md) and the Retry & Recovery Agent contract in [AGENTS.md](../AGENTS.md).

## Retry Philosophy

A retry is an improved engineering attempt based on new information or a changed strategy. Identical retries are forbidden.

Valid retry improvements include:

- additional repository, issue, test, state, memory, or tool evidence;
- changed root-cause hypothesis;
- changed implementation plan;
- changed patch proposal;
- changed validation strategy;
- alternate tool selection;
- alternate agent/model selection;
- prompt constraints refined from failure evidence;
- restored repository checkpoint or corrected base revision.

## Retry Lifecycle

### 1. Failure Detected

A failure is reported by an agent, tool, validation result, test result, state transition, or orchestrator decision.

Required evidence:

- current stage;
- failed operation;
- artifact refs;
- side effects;
- partial outputs;
- confidence snapshot.

### 2. Classify Failure

The failure is mapped to [FAILURE_POLICY.md](FAILURE_POLICY.md). Unknown failures are treated as critical until classified.

Classification must include severity, recoverability, retry eligibility, retry budget, confidence impact, and audit requirements.

### 3. Analyze Root Cause

The Failure Analysis Engine determines what failed, why it likely failed, whether side effects occurred, and which earlier assumption may be invalid.

The analysis must distinguish:

- transient dependency failure;
- insufficient context;
- incorrect root cause;
- bad plan;
- patch mistake;
- tool or model contract failure;
- validation environment problem;
- unsafe repository state.

### 4. Determine Recoverability

The orchestrator evaluates the analysis against policy, state, auditability, safety, and retry history.

Recovery is denied when:

- state integrity is compromised;
- side effects are unknown and unsafe;
- the retry would repeat a prior strategy;
- maximum retry count is reached;
- human approval is required;
- confidence cannot be raised through autonomous evidence.

### 5. Generate Recovery Plan

The Retry & Recovery Agent proposes:

- recovery objective;
- changed strategy;
- additional context to collect;
- target resume stage;
- agent/tool/prompt/patch changes;
- validation needed for the retry;
- rollback or cleanup obligations;
- confidence recalculation plan.

### 6. Collect Missing Context

The workflow resumes at the earliest safe evidence-gathering or planning stage needed to support the changed strategy. The retry system does not gather context itself; it requests the orchestrator to route work to the owning agent.

### 7. Retry Execution

Execution proceeds through normal workflow stages. The retry history remains active so repeated outputs, patches, tools, prompts, or failures can be detected.

### 8. Validate Retry

The retry must be validated against:

- original acceptance criteria;
- failure-specific recovery criteria;
- changed strategy requirements;
- repository safety rules;
- test or validation evidence.

### 9. Decide Outcome

The retry ends in one of:

- `success`: the failure is resolved and workflow can advance;
- `next_retry`: a new, materially different strategy is available and budget remains;
- `escalation`: autonomous recovery is unsafe or exhausted;
- `terminal_failure`: workflow integrity cannot be restored.

## Retry Planning Contract

Every retry plan must define:

- Failure Analysis
- Root Cause Identification
- Recovery Plan
- Additional Context Collection
- Tool Re-selection
- Agent Re-selection
- Prompt Improvement Strategy
- Patch Improvement Strategy
- Confidence Recalculation
- Retry Validation
- Retry Completion Criteria

Any item may be marked `not_applicable` only with rationale.

## Policy Types

### Global Retry Policy

Applies to every workflow. Sets hard limits for retry count, repeated failure detection, unknown failure handling, safety invariants, audit requirements, and escalation.

### Agent Retry Policy

Controls whether an agent may be asked for a revised artifact. Requires changed input, stricter output contract, additional evidence, alternate model policy, or different agent selection.

### Tool Retry Policy

Owned by the Tool Framework. Controls idempotency, side effects, backoff, timeout, malformed output, and alternate tool selection.

### Workflow Retry Policy

Controls legal resume stages, checkpoint selection, state transitions, and retry event emission.

### Validation Retry Policy

Controls retry after diff, semantic, safety, or acceptance validation failure. Requires changed plan or patch evidence.

### Testing Retry Policy

Controls retry after command failure, flaky tests, environment failure, timeout, or dependency issue. Requires failure classification.

### Patch Retry Policy

Controls regeneration or reapplication of patches. Requires base hash checks, approved file scope, duplicate patch detection, and repository cleanup or restore plan.

### Escalation Policy

Controls when retry is forbidden or exhausted and a human/operator packet is required.

## Precedence Rules

1. State integrity and repository safety override every other policy.
2. Security and permission policy override retry eligibility.
3. Human approval requirements override autonomous recovery.
4. Tool idempotency and side-effect policy override retry count availability.
5. Workflow legal transition rules override proposed resume stages.
6. Patch scope and validation policy override patch retry suggestions.
7. More specific policies override broader policies when they are stricter.
8. Global retry policy applies when no specific policy exists.

## Completion Criteria

A retry is complete only when:

- the changed strategy was executed or explicitly abandoned with rationale;
- new evidence was produced or the lack of evidence was recorded;
- confidence was recalculated;
- validation/test expectations were addressed;
- retry history was updated;
- audit events were recorded;
- next action is success, next retry, escalation, or terminal failure.
