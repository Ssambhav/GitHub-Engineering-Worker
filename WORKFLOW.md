# GitHub Engineering Worker Workflow Engine

GitHub Engineering Worker uses a production-grade workflow engine to coordinate agents, tools, state, retries, validation, escalation, and review for the lifecycle of a GitHub Issue. The workflow engine is the central execution model of the platform.

This document is declarative architecture only. It does not implement runtime code, agents, tools, memory, retry logic, state machines, or business logic.

## Workflow Philosophy

The workflow engine must be:

- Event-driven: state changes and decisions are driven by explicit events.
- State-aware: every decision is made against the current execution context and persisted workflow state.
- Deterministic: the same state, artifacts, policies, and events should produce the same next decision.
- Recoverable: failures produce structured recovery paths.
- Interruptible: workflows can pause safely at checkpoints.
- Auditable: every transition has a reason and evidence.
- Restartable: execution can resume from persisted checkpoints.
- Extensible: new stages, agents, tools, and branches can be added through contracts.
- Composable: reusable stage contracts can form larger workflows.

The engine coordinates work. It does not perform repository analysis, code modification, validation, or tool execution directly.

## Execution Lifecycle

The primary engineering workflow starts with a repository and a GitHub Issue and ends in one of four terminal states:

- Completed: review generated after successful or explicitly accepted validation.
- Escalated: human input or approval is required.
- Failed: unrecoverable platform, state, or tool failure.
- Cancelled: execution stopped by external request or policy.

Canonical flow:

```text
Receive Repository
Receive Issue
  -> Understand Issue
  -> Collect Context
  -> Repository Search
  -> Read Relevant Files
  -> Analyze Root Cause
  -> Create Engineering Plan
  -> Generate Patch
  -> Apply Changes
  -> Validate
  -> Run Tests
  -> Decision Point
      -> Retry -> earlier stage with changed strategy
      -> Escalate -> terminal escalation
      -> Review -> Completed
```

The workflow is not a fixed prompt sequence. Each transition is gated by objective criteria, confidence thresholds, artifacts, state, and policy.

## Execution Context

The execution context is the workflow's shared, persisted coordination object. The State Management Agent owns durable state. The Engineering Orchestrator reads and updates it through state tools and workflow events.

Required context fields:

```yaml
workflow_id: stable id
active_issue:
  provider: GitHub
  repository: owner/repo
  issue_number: number
  issue_ref: stable ref
repository:
  ref: repository identifier
  workspace_ref: local or remote workspace ref
  current_revision: commit or content hash
current_stage: stage id
visited_stages:
  - stage id with timestamps
current_objective: concise stage objective
working_context:
  issue_brief_ref: optional
  repository_context_ref: optional
  search_results_ref: optional
  file_excerpt_refs:
    - artifact ref
  root_cause_ref: optional
  plan_ref: optional
  patch_proposal_ref: optional
  applied_change_ref: optional
  validation_report_ref: optional
  test_report_refs:
    - artifact ref
selected_files:
  - path with reason and confidence
selected_agents:
  - agent id and stage
selected_tools:
  - tool id or capability with stage
confidence:
  issue_understanding: high | medium | low
  repository_context: high | medium | low
  root_cause: high | medium | low
  plan: high | medium | low
  patch: high | medium | low
  validation: high | medium | low
  overall: high | medium | low
retry:
  count: integer
  max_allowed: policy-owned value
  last_failure_ref: optional
  changed_strategy_required: true | false
execution_history:
  - event refs and transition refs
temporary_artifacts:
  - artifact refs with retention policy
locks:
  repository_write_lock: optional lock ref
  state_lock: optional lock ref
terminal_summary_ref: optional
```

Ownership:

- State Management Agent owns persistence, locks, checkpoints, and terminal status.
- Engineering Orchestrator owns transition decisions.
- Specialist agents own produced artifacts.
- Audit Logging Agent owns the audit trail.
- Tool Framework owns tool invocation records.

## Stage Contract

Every workflow stage follows a common contract:

```yaml
stage_id: stable stage identifier
purpose: why the stage exists
entry_conditions:
  - required state, artifacts, confidence, permissions, or locks
inputs:
  - artifact refs or context fields
agents_involved:
  - agent ids
allowed_tools:
  - tool categories or capabilities
execution_rules:
  - deterministic constraints for the stage
outputs:
  - required artifact refs or events
exit_conditions:
  success:
    - criteria required to advance
  failure:
    - criteria that route to retry, recovery, escalation, or failure
confidence_updates:
  - confidence fields affected
next_possible_states:
  - stage ids or terminal states
audit_requirements:
  - events, decisions, evidence, and side effects to record
```

## Primary Stage Definitions

### Receive Repository

Purpose: Establish repository identity, access context, and safe workspace boundary.

Entry Conditions: workflow trigger includes repository reference; state can be initialized.

Inputs: repository ref, access policy, runtime constraints.

Outputs: repository context seed, workspace ref, initial state record.

Agents Involved: Engineering Orchestrator, State Management, Audit Logging.

Allowed Tools: State Tools, Audit Tools, Repository Tools, Git Tools in read-only mode.

Success Criteria: repository is identifiable, accessible, and scoped; workflow state initialized.

Failure Criteria: repository missing, inaccessible, unsupported, or unsafe to inspect.

Next Possible States: Receive Issue, Escalated, Failed.

Audit Requirements: record repository ref, access class, scope, and initialization result.

Confidence Updates: repository_context may become low or medium depending on access verification.

### Receive Issue

Purpose: Load the GitHub Issue that defines the engineering objective.

Entry Conditions: repository context exists; issue reference is provided.

Inputs: issue number or issue payload, repository ref.

Outputs: raw issue artifact and issue loaded event.

Agents Involved: Engineering Orchestrator, Issue Understanding, Audit Logging.

Allowed Tools: GitHub Tools, Audit Tools, State Tools.

Success Criteria: issue data is loaded with title, body, metadata, and available discussion refs.

Failure Criteria: issue missing, inaccessible, malformed, or unrelated to repository.

Next Possible States: Understand Issue, Escalated, Failed.

Audit Requirements: record issue ref, loaded fields, access status.

Confidence Updates: issue_understanding remains low until normalized.

### Understand Issue

Purpose: Convert raw issue data into a precise engineering brief.

Entry Conditions: raw issue artifact exists.

Inputs: issue artifact, repository metadata, linked discussion refs.

Outputs: issue brief, acceptance criteria, ambiguity list.

Agents Involved: Issue Understanding Agent, Engineering Orchestrator, Escalation Agent when needed.

Allowed Tools: GitHub Read Tools, Audit Tools, Memory Tools in read mode when relevant.

Success Criteria: issue intent, constraints, expected behavior, and acceptance criteria are stated.

Failure Criteria: insufficient issue data, contradictory requirements, product decision required.

Next Possible States: Collect Context, Escalated.

Audit Requirements: record issue brief ref, assumptions, ambiguity severity, confidence.

Confidence Updates: issue_understanding set based on explicitness and reproducibility.

### Collect Context

Purpose: Build repository-level understanding needed to guide search and validation.

Entry Conditions: issue brief exists with at least medium confidence or an allowed low-confidence exploratory path.

Inputs: issue brief, repository ref, file tree, manifests, docs.

Outputs: repository context summary, candidate areas, build/test entry points.

Agents Involved: Repository Context Agent.

Allowed Tools: Repository Tools, File System Tools in read-only mode, Search Tools for manifests/docs.

Success Criteria: languages, frameworks, conventions, and likely directories are identified.

Failure Criteria: repository too large without indexing, unsupported structure, missing access.

Next Possible States: Repository Search, Escalated, Failed.

Audit Requirements: record inspected manifests/docs, context summary ref, confidence.

Confidence Updates: repository_context increased when conventions and entry points are found.

### Repository Search

Purpose: Locate candidate files, symbols, tests, and documentation relevant to the issue.

Entry Conditions: issue brief and repository context exist.

Inputs: issue brief, repository context, search constraints.

Outputs: ranked search results, query log, candidate file list.

Agents Involved: Repository Search Agent.

Allowed Tools: Search Tools, Repository Tools, File System Tools in read-only mode.

Success Criteria: ranked candidates identify likely implementation and test locations.

Failure Criteria: no candidates found, search too noisy, search tool failure.

Next Possible States: Read Relevant Files, Collect Context, Retry, Escalated.

Audit Requirements: record queries, scopes, result counts, truncation, confidence.

Confidence Updates: repository_context and root_cause readiness increase when results converge.

### Read Relevant Files

Purpose: Read only necessary files or line ranges for root cause analysis and planning.

Entry Conditions: candidate files exist with relevance rationale.

Inputs: ranked search results, file paths, read scopes.

Outputs: file excerpt bundle, dependency pointers, read coverage manifest.

Agents Involved: File Reader Agent.

Allowed Tools: File System Tools, Repository Tools, Search Tools for adjacent references.

Success Criteria: relevant code paths, tests, configs, and adjacent dependencies are covered.

Failure Criteria: missing files, unreadable files, insufficient excerpt coverage, restricted paths.

Next Possible States: Analyze Root Cause, Repository Search, Escalated.

Audit Requirements: record file paths, ranges, hashes, truncation/redaction.

Confidence Updates: root_cause readiness increases with direct evidence coverage.

### Analyze Root Cause

Purpose: Identify why the issue occurs and the minimal behavioral change required.

Entry Conditions: issue brief and file evidence exist.

Inputs: issue brief, repository context, search results, file excerpts.

Outputs: root cause report, evidence map, affected surface area.

Agents Involved: Root Cause Analysis Agent.

Allowed Tools: File System Tools in read-only mode, Search Tools, Validation Tools in read-only diagnostic mode.

Success Criteria: direct evidence links issue symptoms to code path and change target.

Failure Criteria: missing evidence, multiple incompatible hypotheses, undefined product behavior.

Next Possible States: Create Engineering Plan, Read Relevant Files, Repository Search, Escalated.

Audit Requirements: record hypotheses, accepted cause, rejected alternatives, evidence refs.

Confidence Updates: root_cause set to high, medium, or low with rationale.

### Create Engineering Plan

Purpose: Produce a bounded implementation and validation plan.

Entry Conditions: root cause report exists with sufficient confidence.

Inputs: root cause report, issue brief, repository context, file evidence.

Outputs: engineering plan, validation plan, risk assessment.

Agents Involved: Planning Agent, Validation Agent for validation strategy review when needed.

Allowed Tools: Repository Tools and File System Tools in read-only mode, Validation Tools in planning mode.

Success Criteria: plan maps changes to acceptance criteria and identifies validation commands/checks.

Failure Criteria: plan requires unsupported tools, broad refactor, missing acceptance criteria, unsafe risk.

Next Possible States: Generate Patch, Read Relevant Files, Escalated.

Audit Requirements: record plan ref, scope, risks, validation strategy, confidence.

Confidence Updates: plan confidence set from root cause clarity and validation feasibility.

### Generate Patch

Purpose: Design exact intended changes without applying them.

Entry Conditions: engineering plan approved by orchestrator.

Inputs: plan, file excerpts, style conventions, acceptance criteria.

Outputs: patch proposal, change manifest, expected behavioral impact.

Agents Involved: Patch Generation Agent.

Allowed Tools: File System Tools in read-only mode, Validation Tools for syntax/style reference.

Success Criteria: patch proposal is minimal, scoped, and applicable by Code Modification.

Failure Criteria: insufficient file context, ambiguous edit target, scope drift.

Next Possible States: Apply Changes, Read Relevant Files, Create Engineering Plan, Escalated.

Audit Requirements: record patch proposal ref, files intended to change, rationale.

Confidence Updates: patch confidence reflects precision and scope safety.

### Apply Changes

Purpose: Apply orchestrator-approved modifications to the repository.

Entry Conditions: patch proposal approved; repository write lock acquired; dirty-state policy satisfied.

Inputs: approved patch proposal, target files, base hashes, lock token.

Outputs: applied change manifest, diff summary, changed files.

Agents Involved: Code Modification Agent, State Management Agent, Audit Logging Agent.

Allowed Tools: Code Modification Tools, File System Tools with write scope, Git Tools in read/diff mode, State Tools, Audit Tools.

Success Criteria: changes apply cleanly and only approved files are modified.

Failure Criteria: patch conflict, base mismatch, unauthorized file change, unsafe dirty state.

Next Possible States: Validate, Generate Patch, Retry, Escalated.

Audit Requirements: record lock, patch ref, changed files, base hashes, diff ref, side effects.

Confidence Updates: patch confidence increases if applied diff matches proposal; decreases on drift.

### Validate

Purpose: Inspect the applied change against plan, acceptance criteria, style, and safety rules.

Entry Conditions: applied change manifest and diff summary exist.

Inputs: issue brief, plan, patch proposal, diff summary, changed files.

Outputs: validation report, required test commands, residual risks.

Agents Involved: Validation Agent.

Allowed Tools: Validation Tools, Search Tools, File System Tools in read-only mode, Git Tools in diff mode.

Success Criteria: diff is scoped, coherent, style-compatible, and test strategy is sufficient.

Failure Criteria: diff exceeds scope, acceptance criteria not addressed, safety risk, missing tests.

Next Possible States: Run Tests, Generate Patch, Retry, Escalated.

Audit Requirements: record validation checks, diff refs, pass/fail decision, risk list.

Confidence Updates: validation confidence set based on static and semantic evidence.

### Run Tests

Purpose: Execute approved tests and checks and capture factual results.

Entry Conditions: validation plan identifies approved commands; command permissions granted.

Inputs: test command list, environment constraints, timeout policy, repository state.

Outputs: test execution report, command evidence, failure classifications.

Agents Involved: Test Execution Agent, Validation Agent.

Allowed Tools: Testing Tools, Validation Tools, System Tools, Git Tools in read-only mode.

Success Criteria: relevant commands complete and results are captured with exit codes and output refs.

Failure Criteria: test failure, environment failure, timeout, dependency failure, unsafe command.

Next Possible States: Decision Point, Retry, Escalated.

Audit Requirements: record command, duration, exit code, output refs, truncation, environment notes.

Confidence Updates: validation and overall confidence increase on relevant passes; decrease on failures.

### Decision Point

Purpose: Decide whether to retry, escalate, review, or fail.

Entry Conditions: validation and test reports exist, or a structured failure prevents them.

Inputs: all current artifacts, confidence, retry history, failure reports, policy.

Outputs: transition decision, decision rationale, next stage or terminal status.

Agents Involved: Engineering Orchestrator, Retry & Recovery Agent, Escalation Agent, Review Generation Agent as needed.

Allowed Tools: State Tools, Audit Tools, Memory Tools, Git Tools in read-only mode.

Success Criteria: next action is deterministic, justified, and recorded.

Failure Criteria: state inconsistency, missing required artifacts, unknown unsafe failure.

Next Possible States: Retry, Escalated, Review, Failed.

Audit Requirements: record decision criteria, confidence rollup, retry eligibility, terminal rationale.

Confidence Updates: overall confidence finalized or routed for recovery.

### Retry

Purpose: Recover from failure with a changed strategy.

Entry Conditions: failure is recoverable; retry budget available; changed strategy is identified.

Inputs: failure report, retry history, current artifacts, state snapshot.

Outputs: recovery recommendation, retry plan, target resume stage.

Agents Involved: Retry & Recovery Agent, Engineering Orchestrator.

Allowed Tools: Audit Tools, State Tools, read-only diagnostic tools relevant to failure.

Success Criteria: retry resumes at the earliest safe stage with changed evidence, scope, or hypothesis.

Failure Criteria: max retry reached, repeated strategy, unsafe uncertainty, unrecoverable failure.

Next Possible States: Repository Search, Read Relevant Files, Analyze Root Cause, Create Engineering Plan, Generate Patch, Apply Changes, Validate, Run Tests, Escalated, Failed.

Audit Requirements: record failure category, retry count, changed strategy, resume stage.

Confidence Updates: confidence may be lowered until new evidence confirms recovery.

### Escalate

Purpose: Produce a human-actionable escalation when autonomous continuation is unsafe.

Entry Conditions: human decision, permission, access, product clarification, or safety intervention is required.

Inputs: blocker report, artifacts, confidence, retry history, risk summary.

Outputs: escalation packet, human question or decision request, terminal state if paused.

Agents Involved: Escalation Agent, Review Generation Agent for handoff summary, Orchestrator.

Allowed Tools: Audit Tools, State Tools, notification tools only when authorized.

Success Criteria: human can decide next step without reconstructing the workflow.

Failure Criteria: insufficient evidence to frame escalation.

Next Possible States: Escalated terminal, or suspended awaiting human response.

Audit Requirements: record escalation reason, evidence, requested decision, urgency.

Confidence Updates: overall confidence marked blocked or low.

### Review

Purpose: Produce the final engineering review.

Entry Conditions: validation/test decision supports completion, or escalation/failure requires final summary.

Inputs: issue brief, root cause report, plan, diff summary, validation report, test report, audit highlights.

Outputs: engineering review, completion summary, optional PR/issue response draft.

Agents Involved: Review Generation Agent, Orchestrator, Audit Logging.

Allowed Tools: File System Tools in read-only mode, Git Tools in diff/status mode, Audit Tools, State Tools.

Success Criteria: review explains issue, cause, changes, validation, limitations, and residual risk.

Failure Criteria: missing essential artifacts, unresolved critical validation risk.

Next Possible States: Completed, Escalated, Failed.

Audit Requirements: record review ref and terminal summary.

Confidence Updates: overall confidence finalized.

### Completed

Purpose: Safely terminate the workflow after review generation.

Entry Conditions: final review exists and terminal state transition is legal.

Inputs: final review, state snapshot, audit trail.

Outputs: completed terminal state, closed audit trail.

Agents Involved: Orchestrator, State Management, Audit Logging, Memory Management when learning is proposed.

Allowed Tools: State Tools, Audit Tools, Memory Tools for proposed updates.

Success Criteria: terminal state persisted and final summary available.

Failure Criteria: state/audit closure failure.

Next Possible States: none.

Audit Requirements: record final state, artifact refs, confidence, limitations.

Confidence Updates: no further updates after terminal state.

## Decision Engine

The Decision Engine is a deterministic policy evaluator used by the orchestrator. It consumes current state, artifacts, events, confidence, retry history, and policy to select the next transition.

### Decision Inputs

- Current stage and legal next states.
- Required artifact availability and freshness.
- Confidence fields and thresholds.
- Failure category and recoverability.
- Retry count and strategy history.
- Tool permissions and safety constraints.
- Repository dirty state and locks.
- Validation/test outcomes.
- Escalation policy.

### Objective Criteria

Enough context exists when:

- Issue brief has explicit or inferable acceptance criteria.
- Repository context identifies likely modules and validation entry points.
- Search results converge on a bounded set of files or symbols.
- File excerpts cover the suspected control flow and relevant tests/config.

Additional files should be read when:

- Root cause confidence is below threshold due to missing code path evidence.
- Search results identify dependencies not yet inspected.
- Patch generation cannot identify exact edit locations.
- Validation identifies uninspected affected surface area.

Repository search should repeat when:

- File reads disprove the current hypothesis.
- Search results are noisy or incomplete.
- New domain terms are discovered from code.
- Tests/config references suggest additional modules.

Validation should continue when:

- Applied diff matches plan.
- Required validation commands are available.
- No critical safety or scope issue is present.
- Test execution can add meaningful confidence.

Retry should occur when:

- Failure is retryable or retry_with_changes.
- Retry budget remains.
- A changed strategy is available.
- Side effects are understood and safe.

Escalation should occur when:

- Product intent is ambiguous.
- Required permission/access is missing.
- Repository safety is compromised.
- Validation cannot establish acceptable safety.
- Retry budget is exhausted.
- Failure category is critical or unknown with unsafe side effects.

Termination should occur when:

- Final review or escalation packet exists.
- Terminal state transition succeeds.
- Audit closure is recorded.
- No required cleanup remains.

## Branching Model

### Validation Success

Condition: validation report passes and required tests are either passed or explicitly not applicable with rationale.

Resume: Review.

### Validation Failure

Condition: diff violates plan, safety, style, acceptance mapping, or coverage expectations.

Resume: Retry if recoverable; Generate Patch or Create Engineering Plan if strategy changes; Escalate if unsafe.

### Test Failure

Condition: approved test command completes with failing exit status.

Resume: Retry through Root Cause Analysis, Planning, or Patch Generation depending on failure classification.

### Repository Error

Condition: repository state is inaccessible, inconsistent, locked, or corrupted.

Resume: Collect Context after refresh if recoverable; Escalate or Failed if unsafe.

### Missing Context

Condition: analysis or planning cannot proceed due to absent evidence.

Resume: Repository Search or Read Relevant Files.

### Tool Failure

Condition: tool response has structured failure.

Resume: same stage if retryable and idempotent; alternate tool if available; Retry & Recovery; Escalate on permission or contract failure.

### Low Confidence

Condition: confidence below threshold for next stage.

Resume: earlier evidence-gathering stage appropriate to the weak confidence field.

### Unsafe Modification

Condition: patch would modify unapproved files, conflict with dirty state, or exceed scope.

Resume: Generate Patch if correctable; Escalate if local state or scope is unsafe.

### Human Approval Required

Condition: policy requires human approval for permission, broad change, external action, or product decision.

Resume: Suspended/Escalated until human response; then resume from stage indicated by response.

### Maximum Retry Reached

Condition: retry count equals policy limit or strategies repeat.

Resume: Escalate with retry history.

### Unknown Failure

Condition: failure category is unknown, malformed, or cannot be classified safely.

Resume: Retry & Recovery for one diagnostic pass if safe; otherwise Escalate or Failed.

## Workflow Events

Events are immutable facts emitted by agents, tools, state management, or the orchestrator.

| Event | Publisher | Subscribers |
| --- | --- | --- |
| WorkflowStarted | Orchestrator | State Management, Audit Logging |
| RepositoryLoaded | Repository Context / Orchestrator | State Management, Audit Logging |
| IssueLoaded | Issue Understanding / GitHub Tool | Orchestrator, Audit Logging |
| IssueUnderstood | Issue Understanding | Orchestrator, State Management, Audit Logging |
| ContextCollected | Repository Context | Orchestrator, Repository Search, Audit Logging |
| SearchCompleted | Repository Search | Orchestrator, File Reader, Audit Logging |
| FilesRead | File Reader | Orchestrator, Root Cause Analysis, Audit Logging |
| AnalysisCompleted | Root Cause Analysis | Orchestrator, Planning, Audit Logging |
| PlanApproved | Orchestrator | Patch Generation, State Management, Audit Logging |
| PatchGenerated | Patch Generation | Orchestrator, Code Modification, Audit Logging |
| PatchApplied | Code Modification | Orchestrator, Validation, State Management, Audit Logging |
| ValidationSucceeded | Validation | Orchestrator, Review Generation, Audit Logging |
| ValidationFailed | Validation | Orchestrator, Retry & Recovery, Audit Logging |
| TestsPassed | Test Execution | Orchestrator, Validation, Audit Logging |
| TestsFailed | Test Execution | Orchestrator, Retry & Recovery, Validation, Audit Logging |
| RetryStarted | Orchestrator / Retry & Recovery | State Management, Audit Logging |
| RetryCompleted | Retry & Recovery | Orchestrator, State Management, Audit Logging |
| EscalationStarted | Escalation Agent | Orchestrator, State Management, Audit Logging |
| ReviewGenerated | Review Generation | Orchestrator, State Management, Audit Logging |
| WorkflowCompleted | Orchestrator | State Management, Audit Logging, Memory Management |
| WorkflowFailed | Orchestrator | State Management, Audit Logging |

## Parallelism

The engine may run stages concurrently only when they are read-only or operate on independent artifacts.

Allowed parallel work:

- Repository structure inspection and issue discussion normalization after initial repository/issue load.
- Repository search across independent query sets.
- Documentation analysis and test discovery during context collection.
- Dependency analysis and file read planning in read-only mode.
- Validation preparation while patch proposal is being reviewed, if it does not assume unapplied changes.

Not parallel:

- Code modification with any other repository write.
- Test execution before patch application and validation strategy approval.
- Terminal review before validation decision.
- State transitions that mutate the same workflow state.

Synchronization rules:

- State Management owns locks and checkpoints.
- Orchestrator joins parallel results before decision points.
- Conflicting outputs are resolved by evidence comparison or targeted follow-up.
- Parallel tasks must emit events with correlation ids and artifact refs.

## Checkpoints

Checkpoints allow pause, resume, restart, recovery, rollback planning, and safe termination.

Checkpoint types:

- Intake checkpoint: repository and issue loaded.
- Understanding checkpoint: issue brief and acceptance criteria produced.
- Context checkpoint: repository context and search strategy produced.
- Evidence checkpoint: file excerpts and evidence map produced.
- Analysis checkpoint: root cause report produced.
- Plan checkpoint: engineering plan and validation plan produced.
- Patch checkpoint: patch proposal produced.
- Modification checkpoint: applied change manifest and diff summary produced.
- Validation checkpoint: validation/test reports produced.
- Decision checkpoint: retry/escalation/review decision recorded.
- Terminal checkpoint: final review, escalation packet, or failure summary recorded.

Each checkpoint persists:

- Workflow id and current stage.
- Repository revision and workspace ref.
- Artifact refs and versions.
- Confidence snapshot.
- Retry count and failure refs.
- Locks held or released.
- Tool invocation refs.
- Audit refs.
- Cleanup obligations.

Rollback is a policy-governed recovery action. The workflow architecture records rollback requirements and safe restore points but does not implement rollback logic.

## Safety Rules

- Never modify code before issue understanding, context collection, file evidence, root cause analysis, and plan approval.
- Never apply changes without an approved patch proposal and repository write lock.
- Never execute validation commands before patch generation and validation strategy selection.
- Never commit code before successful validation and explicit commit authorization.
- Never retry a failed path without changed evidence, input, scope, hypothesis, or strategy.
- Never escalate before bounded retry when failure is safely recoverable.
- Escalate immediately when repository safety, permission integrity, auditability, or product intent is compromised.
- Never terminate without a final execution summary, review, escalation packet, or failure report.
- Never hide partial side effects, skipped cleanup, or validation gaps.

## Extension Guidelines

New workflows or stages must:

- Use the stage contract.
- Declare entry and exit conditions.
- Define allowed agents and tool capabilities.
- Emit events and audit records.
- Define confidence updates.
- Define branches and terminal behavior.
- Preserve deterministic decision criteria.
- Avoid embedding prompts, business logic, or runtime code.

Workflow extensions should be composable. A new specialized workflow should reuse existing stages where possible and add only the stages needed for a distinct lifecycle.
