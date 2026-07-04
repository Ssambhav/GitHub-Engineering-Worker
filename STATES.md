# GitHub Engineering Worker State Machine

GitHub Engineering Worker uses a deterministic execution state machine to control where a workflow instance is in the lifecycle of a GitHub Issue. The workflow defines what engineering work happens. The state machine defines the single authoritative primary state, the legal transitions out of that state, and the evidence required to move.

This document is declarative architecture and implementation scaffolding only. It does not implement runtime execution, agents, workflows, retry logic, or tools.

## State Philosophy

Every workflow execution must exist in exactly one primary state. A state is not a vague phase label; it is a persisted control position with explicit entry requirements, permitted operations, valid exits, confidence effects, audit obligations, timeout expectations, and recovery behavior.

Core rules:

- One primary state is active at a time.
- Transitions are explicit, validated, logged, and deterministic.
- Every transition has a trigger, reason, actor, evidence, and audit record.
- No state is entered implicitly as a side effect of tool or agent completion.
- Terminal states are immutable except through administrative archival metadata.
- Specialist agents produce artifacts; the state machine controls lifecycle position.
- State persists independently of process memory and agent context.

## Complete State Catalog

The canonical primary states are:

| State | Purpose | Terminal |
| --- | --- | --- |
| `IDLE` | Workflow record exists but execution has not started. | No |
| `INITIALIZING` | Establish workflow identity, state record, locks, audit trail, and seed memory. | No |
| `UNDERSTAND_ISSUE` | Convert raw issue data into an engineering brief and acceptance criteria. | No |
| `CLONE_REPOSITORY` | Establish a safe repository workspace and revision identity. | No |
| `COLLECT_CONTEXT` | Build repository-level context, conventions, and validation entry points. | No |
| `SEARCH_REPOSITORY` | Find candidate files, symbols, tests, and docs. | No |
| `READ_FILES` | Read bounded file excerpts needed for analysis and planning. | No |
| `ANALYZE` | Identify root cause, affected surface, and minimal change target. | No |
| `PLAN` | Produce implementation and validation plan. | No |
| `GENERATE_PATCH` | Produce a patch proposal without applying changes. | No |
| `APPLY_PATCH` | Apply approved modifications under lock. | No |
| `VALIDATE` | Inspect diff and decide required checks. | No |
| `RUN_TESTS` | Execute approved tests/checks and capture results. | No |
| `RETRY` | Route recoverable failure to a changed strategy and safe resume state. | No |
| `GENERATE_REVIEW` | Produce final engineering review or handoff summary. | No |
| `ESCALATE` | Prepare human-actionable escalation and pause or terminate autonomously. | No |
| `COMPLETED` | Successful terminal state after review and closure. | Yes |
| `FAILED` | Unrecoverable terminal state with failure report. | Yes |
| `CANCELLED` | External or policy cancellation terminal state. | Yes |

Detailed reusable state definitions live in [states/definitions/primary-states.yaml](states/definitions/primary-states.yaml).

## State Details

### `IDLE`

Purpose: Hold a created workflow instance before active execution.

Entry Conditions: workflow id allocated; repository and issue references are present or expected; no terminal state exists.

Exit Conditions: execution start is requested and initialization preconditions are satisfied, or cancellation is requested.

Allowed Operations: inspect trigger payload, validate basic request shape, accept cancellation.

Allowed Agents: Engineering Orchestrator, State Management Agent, Audit Logging Agent.

Allowed Tools: State Tools, Audit Tools, read-only configuration tools.

Required Memory: none required; optional prior workflow lookup may be referenced.

Generated Events: `StateEntered`, `WorkflowStarted`, `TransitionStarted`, `TransitionCompleted`, `WorkflowCancelled`.

Failure Conditions: malformed trigger, duplicate active workflow, missing correlation id, state store unavailable.

Recovery Strategy: reject start, deduplicate by idempotency key, or route to `FAILED` if state cannot be trusted.

Confidence Impact: overall confidence remains `unknown`.

Audit Requirements: record trigger identity, repository ref, issue ref, actor, idempotency key, and start/cancel reason.

Timeout Expectations: short; initialization should be requested promptly or the record may expire by policy.

Retry Eligibility: not retryable as engineering work; duplicate starts must be idempotent.

Success Criteria: legal transition to `INITIALIZING` is recorded.

Next Valid States: `INITIALIZING`, `CANCELLED`, `FAILED`.

Invalid Transitions: any engineering state, `COMPLETED`, `ESCALATE`, or `RETRY`.

### `INITIALIZING`

Purpose: Create the authoritative execution context, locks, audit trail, checkpoint seed, and memory snapshot.

Entry Conditions: legal transition from `IDLE`; workflow id and trigger payload exist; state lock can be acquired.

Exit Conditions: state record, audit correlation, policy snapshot, and initial context are persisted.

Allowed Operations: initialize state, load policies, create audit trail, retrieve relevant memory, validate required refs.

Allowed Agents: Engineering Orchestrator, State Management Agent, Audit Logging Agent, Memory Management Agent.

Allowed Tools: State Tools, Audit Tools, Memory Read Tools, Configuration Tools.

Required Memory: repository memory lookup, related issue memory lookup, prior failure patterns if available.

Generated Events: `StateEntered`, `WorkflowInitialized`, `MemoryRetrieved`, `CheckpointCreated`, `StateExited`.

Failure Conditions: missing repository/issue ref, permission denial, audit sink unavailable, state lock conflict.

Recovery Strategy: retry initialization only when idempotency key proves no conflicting workflow; otherwise escalate or fail.

Confidence Impact: establishes baseline confidence fields as `unknown` or `low`.

Audit Requirements: record initialized fields, policy versions, memory refs, lock refs, and denied prerequisites.

Timeout Expectations: short to medium.

Retry Eligibility: retryable for transient state/audit/memory failures; not retryable for invalid input.

Success Criteria: initial checkpoint and execution context exist.

Next Valid States: `UNDERSTAND_ISSUE`, `CLONE_REPOSITORY`, `ESCALATE`, `FAILED`, `CANCELLED`.

Invalid Transitions: patching, validation, terminal completion, or retry before any failure artifact exists.

### `UNDERSTAND_ISSUE`

Purpose: Normalize the GitHub Issue into a bounded engineering brief.

Entry Conditions: initialized context exists; issue ref or raw issue artifact is available.

Exit Conditions: issue brief, acceptance criteria, assumptions, ambiguity list, and confidence are recorded.

Allowed Operations: read issue data, parse title/body/comments/labels, identify requirements, classify ambiguity.

Allowed Agents: Issue Understanding Agent, Engineering Orchestrator, Escalation Agent when ambiguity is blocking.

Allowed Tools: GitHub Read Tools, Markdown/Attachment Readers, Memory Read Tools, Audit Tools, State Tools.

Required Memory: issue summary memory, related prior issue memory, repository-specific issue patterns when safe.

Generated Events: `IssueLoaded`, `IssueUnderstood`, `StateExited`, `TransitionRejected` when brief is insufficient.

Failure Conditions: inaccessible issue, contradictory requirements, no actionable problem, product decision required.

Recovery Strategy: retry issue read if transient; ask for human clarification through `ESCALATE` for product ambiguity.

Confidence Impact: updates `issue_understanding`; low confidence blocks modification states.

Audit Requirements: record issue refs, loaded fields, assumptions, ambiguity severity, and brief artifact ref.

Timeout Expectations: medium; dependent on GitHub/API access and attachment availability.

Retry Eligibility: retryable for transient GitHub failures; not retryable for missing product intent without new input.

Success Criteria: issue intent and acceptance criteria are testable enough to guide repository work.

Next Valid States: `CLONE_REPOSITORY`, `COLLECT_CONTEXT`, `ESCALATE`, `FAILED`, `CANCELLED`.

Invalid Transitions: `GENERATE_PATCH`, `APPLY_PATCH`, `VALIDATE`, `RUN_TESTS`, `COMPLETED`.

### `CLONE_REPOSITORY`

Purpose: Establish a safe local or remote workspace for the target repository and revision.

Entry Conditions: initialized context exists; repository ref is available; repository access policy permits checkout or attachment.

Exit Conditions: workspace ref, repository revision, dirty-state baseline, and repository scope are persisted.

Allowed Operations: resolve repository, create or attach workspace, verify revision, inspect safe metadata.

Allowed Agents: Repository Context Agent, Engineering Orchestrator, State Management Agent.

Allowed Tools: Repository Tools, Git Tools, File System Tools in workspace-scoped mode, Audit Tools, State Tools.

Required Memory: repository metadata memory, known generated paths, known safe/unsafe workspace rules.

Generated Events: `RepositoryLoaded`, `WorkspacePrepared`, `CheckpointCreated`, `StateExited`.

Failure Conditions: repository inaccessible, unsupported VCS, unsafe workspace, checkout failure, policy denial.

Recovery Strategy: retry with refreshed credentials or alternate workspace if policy allows; otherwise escalate or fail.

Confidence Impact: updates repository access and context readiness.

Audit Requirements: record repository ref, revision, workspace ref, access class, and scope boundary.

Timeout Expectations: medium to long depending on repository size and network.

Retry Eligibility: retryable for transient network/VCS failures; not retryable for permission denial without new authorization.

Success Criteria: repository workspace is safely addressable and revision is known.

Next Valid States: `COLLECT_CONTEXT`, `UNDERSTAND_ISSUE`, `ESCALATE`, `FAILED`, `CANCELLED`.

Invalid Transitions: modification, validation, review, and completion states.

### `COLLECT_CONTEXT`

Purpose: Build repository topology, conventions, manifests, validation entry points, and likely ownership areas.

Entry Conditions: repository workspace exists; issue brief exists or exploratory context collection is policy-approved.

Exit Conditions: repository context summary and candidate directories are persisted.

Allowed Operations: read manifests/docs, inspect file tree, identify languages/frameworks/tests, record conventions.

Allowed Agents: Repository Context Agent, File Reader Agent for bounded docs, Engineering Orchestrator.

Allowed Tools: Repository Tools, Search Tools, File System Read Tools, Manifest Readers, Audit Tools, State Tools.

Required Memory: repository structure memory, validation command memory, known conventions, generated path memory.

Generated Events: `ContextCollected`, `RepositoryMapped`, `CheckpointCreated`, `StateExited`.

Failure Conditions: unreadable repository structure, unsupported layout, missing manifests, excessive size without index.

Recovery Strategy: narrow context scope, use index/search if available, or escalate if topology cannot be classified.

Confidence Impact: updates `repository_context`.

Audit Requirements: record inspected manifests/docs, ignored paths, candidate areas, and context artifact ref.

Timeout Expectations: medium.

Retry Eligibility: retryable with narrowed scope or alternate search/index strategy.

Success Criteria: downstream search and validation can be scoped.

Next Valid States: `SEARCH_REPOSITORY`, `READ_FILES`, `ESCALATE`, `FAILED`, `CANCELLED`.

Invalid Transitions: `APPLY_PATCH`, `RUN_TESTS`, `COMPLETED`.

### `SEARCH_REPOSITORY`

Purpose: Locate candidate implementation files, tests, symbols, and documentation relevant to the issue.

Entry Conditions: issue brief and repository context exist; search scope is defined.

Exit Conditions: ranked results, query log, candidate files, and gaps are persisted.

Allowed Operations: run targeted search, rank hits, refine terms, identify tests/docs/call sites.

Allowed Agents: Repository Search Agent, Engineering Orchestrator.

Allowed Tools: Search Tools, Repository Tools, File System Read Tools, Audit Tools, State Tools.

Required Memory: search results memory, repository vocabulary, prior related issue patterns.

Generated Events: `SearchStarted`, `SearchCompleted`, `SearchNoMatch`, `CheckpointCreated`.

Failure Conditions: search unavailable, result set too noisy, no plausible candidates, index corruption.

Recovery Strategy: return to `COLLECT_CONTEXT`, broaden/narrow queries, or escalate after bounded attempts.

Confidence Impact: increases root-cause readiness when results converge; decreases when noisy or empty.

Audit Requirements: record queries, scopes, result counts, truncation, and ranking rationale.

Timeout Expectations: short to medium.

Retry Eligibility: retryable with changed query, scope, or index/tool.

Success Criteria: enough candidate files exist to read targeted evidence.

Next Valid States: `READ_FILES`, `COLLECT_CONTEXT`, `RETRY`, `ESCALATE`, `FAILED`, `CANCELLED`.

Invalid Transitions: `APPLY_PATCH`, `VALIDATE`, `RUN_TESTS`, `COMPLETED`.

### `READ_FILES`

Purpose: Read only bounded files or line ranges needed for root cause analysis and planning.

Entry Conditions: candidate files or docs exist with relevance rationale.

Exit Conditions: file excerpts, hashes, ranges, summaries, and follow-up pointers are persisted.

Allowed Operations: read files, summarize behavior, identify imports/call sites/tests, validate excerpt sufficiency.

Allowed Agents: File Reader Agent, Repository Search Agent for adjacent references, Engineering Orchestrator.

Allowed Tools: File System Read Tools, Repository Tools, Search Tools, Audit Tools, State Tools.

Required Memory: files visited memory, search result refs, repository structure refs.

Generated Events: `FilesRead`, `FileReadSkipped`, `EvidenceCollected`, `CheckpointCreated`.

Failure Conditions: missing/unreadable/generated/binary files, insufficient ranges, restricted paths.

Recovery Strategy: adjust read scope, return to search, or escalate restricted/unsafe evidence gaps.

Confidence Impact: improves root-cause readiness with direct control-flow evidence.

Audit Requirements: record file paths, ranges, hashes, reasons, truncation, and redaction status.

Timeout Expectations: short to medium.

Retry Eligibility: retryable with changed file set or range.

Success Criteria: relevant implementation, tests, config, and adjacent dependencies are covered.

Next Valid States: `ANALYZE`, `SEARCH_REPOSITORY`, `COLLECT_CONTEXT`, `ESCALATE`, `FAILED`, `CANCELLED`.

Invalid Transitions: `APPLY_PATCH`, `RUN_TESTS`, `COMPLETED`.

### `ANALYZE`

Purpose: Identify the root cause and minimal behavior change target.

Entry Conditions: issue brief and file evidence exist.

Exit Conditions: root cause report, evidence map, affected surface, and confidence are persisted.

Allowed Operations: compare hypotheses to evidence, reject alternatives, identify change target and non-goals.

Allowed Agents: Root Cause Analysis Agent, File Reader Agent for requested gaps, Engineering Orchestrator.

Allowed Tools: File System Read Tools, Search Tools, Static Diagnostics, Audit Tools, State Tools.

Required Memory: analysis memory, files visited memory, confidence history.

Generated Events: `AnalysisStarted`, `AnalysisCompleted`, `HypothesisRejected`, `CheckpointCreated`.

Failure Conditions: missing evidence, conflicting causes, product behavior undefined, stale repository revision.

Recovery Strategy: return to `READ_FILES` or `SEARCH_REPOSITORY`; escalate product ambiguity.

Confidence Impact: sets `root_cause`.

Audit Requirements: record accepted cause, rejected alternatives, evidence refs, and confidence rationale.

Timeout Expectations: medium.

Retry Eligibility: retryable only with new evidence, hypothesis, or issue clarification.

Success Criteria: cause and change target are specific enough for planning.

Next Valid States: `PLAN`, `READ_FILES`, `SEARCH_REPOSITORY`, `RETRY`, `ESCALATE`, `FAILED`, `CANCELLED`.

Invalid Transitions: `APPLY_PATCH`, `RUN_TESTS`, `COMPLETED`.

### `PLAN`

Purpose: Produce bounded implementation and validation plans.

Entry Conditions: root cause confidence meets threshold or a policy-approved exploratory plan is allowed.

Exit Conditions: engineering plan, validation plan, risk assessment, and acceptance mapping are persisted.

Allowed Operations: define scoped changes, validation commands, rollback obligations, and risk controls.

Allowed Agents: Planning Agent, Validation Agent for strategy review, Engineering Orchestrator.

Allowed Tools: Repository Read Tools, Validation Planning Tools, Audit Tools, State Tools.

Required Memory: planning memory, repository conventions, validation command memory.

Generated Events: `PlanProposed`, `PlanApproved`, `PlanRejected`, `CheckpointCreated`.

Failure Conditions: unsafe scope, unsupported tools, missing acceptance criteria, unclear rollback obligations.

Recovery Strategy: return to analysis/evidence gathering or escalate architectural/product decisions.

Confidence Impact: sets `plan` and may update `overall`.

Audit Requirements: record plan ref, approval reason, scope boundaries, risks, and validation strategy.

Timeout Expectations: medium.

Retry Eligibility: retryable with changed scope, evidence, or validation strategy.

Success Criteria: plan is concrete enough to generate a patch proposal.

Next Valid States: `GENERATE_PATCH`, `ANALYZE`, `READ_FILES`, `RETRY`, `ESCALATE`, `FAILED`, `CANCELLED`.

Invalid Transitions: `APPLY_PATCH`, `RUN_TESTS`, `COMPLETED`.

### `GENERATE_PATCH`

Purpose: Produce precise intended code changes without mutating repository content.

Entry Conditions: plan is approved; target files and style context are available.

Exit Conditions: patch proposal, change manifest, expected behavior, and applicability notes are persisted.

Allowed Operations: design edits, identify target functions/tests/docs, validate scope against plan.

Allowed Agents: Patch Generation Agent, File Reader Agent for missing context, Engineering Orchestrator.

Allowed Tools: File System Read Tools, Diff Planning Tools, Validation Reference Tools, Audit Tools, State Tools.

Required Memory: generated patch memory, planning memory, repository convention memory.

Generated Events: `PatchGenerated`, `PatchRejected`, `CheckpointCreated`, `StateExited`.

Failure Conditions: ambiguous edit location, insufficient context, scope drift, proposal violates policy.

Recovery Strategy: return to `PLAN` or `READ_FILES`; escalate if change cannot be scoped.

Confidence Impact: sets `patch` proposal confidence.

Audit Requirements: record patch proposal ref, intended changed files, base hashes, and rationale.

Timeout Expectations: medium.

Retry Eligibility: retryable with changed plan, file context, or patch strategy.

Success Criteria: proposal is minimal, scoped, and ready for authorized application.

Next Valid States: `APPLY_PATCH`, `PLAN`, `READ_FILES`, `RETRY`, `ESCALATE`, `FAILED`, `CANCELLED`.

Invalid Transitions: `RUN_TESTS`, `COMPLETED`.

### `APPLY_PATCH`

Purpose: Apply approved repository modifications under state and repository write controls.

Entry Conditions: patch proposal approved; repository write lock acquired; base hashes and dirty-state policy pass.

Exit Conditions: applied change manifest, diff summary, file hashes, and side-effect report are persisted.

Allowed Operations: edit approved files, run approved formatters only if declared, inspect diff/status.

Allowed Agents: Code Modification Agent, State Management Agent, Audit Logging Agent, Engineering Orchestrator.

Allowed Tools: Code Modification Tools, File System Write Tools scoped to approved files, Git Diff Tools, State Tools, Audit Tools.

Required Memory: files modified memory, generated patch memory, workflow decision memory.

Generated Events: `PatchApplyStarted`, `PatchApplied`, `PatchApplyFailed`, `CheckpointCreated`.

Failure Conditions: conflict, base mismatch, unauthorized file mutation, dirty-state conflict, formatter side effects.

Recovery Strategy: release or preserve locks according to policy, return to `GENERATE_PATCH`, enter `RETRY`, or escalate unsafe state.

Confidence Impact: patch confidence increases when diff matches proposal; decreases on drift.

Audit Requirements: record lock refs, base hashes, changed files, diff refs, side effects, and cleanup obligations.

Timeout Expectations: medium.

Retry Eligibility: retryable only after conflict classification and changed patch/application strategy.

Success Criteria: only approved changes are applied cleanly.

Next Valid States: `VALIDATE`, `GENERATE_PATCH`, `RETRY`, `ESCALATE`, `FAILED`, `CANCELLED`.

Invalid Transitions: `COMPLETED` without validation/review, `RUN_TESTS` before validation.

### `VALIDATE`

Purpose: Evaluate applied diff against plan, acceptance criteria, style, and safety rules.

Entry Conditions: applied change manifest and diff summary exist.

Exit Conditions: validation report, required checks, residual risks, and pass/fail decision are persisted.

Allowed Operations: inspect diff, map acceptance criteria, check scope/style/static rules, approve test commands.

Allowed Agents: Validation Agent, Test Execution Agent for command feasibility, Engineering Orchestrator.

Allowed Tools: Validation Tools, Git Diff Tools, File System Read Tools, Search Tools, Audit Tools, State Tools.

Required Memory: validation memory, files modified memory, planning memory.

Generated Events: `ValidationStarted`, `ValidationSucceeded`, `ValidationFailed`, `CheckpointCreated`.

Failure Conditions: diff exceeds scope, acceptance gap, unsafe side effect, missing validation path.

Recovery Strategy: route to `GENERATE_PATCH`, `PLAN`, `RETRY`, or `ESCALATE` based on recoverability.

Confidence Impact: sets `validation`; may update `overall`.

Audit Requirements: record checks performed, evidence refs, failures, skipped checks, and rationale.

Timeout Expectations: medium.

Retry Eligibility: retryable with changed patch, plan, or validation strategy.

Success Criteria: diff is coherent and test/check strategy is approved or explicitly not applicable.

Next Valid States: `RUN_TESTS`, `GENERATE_PATCH`, `PLAN`, `RETRY`, `ESCALATE`, `FAILED`, `CANCELLED`.

Invalid Transitions: `COMPLETED` without review, earlier intake states unless recovery explicitly routes there.

### `RUN_TESTS`

Purpose: Execute approved commands and capture factual results.

Entry Conditions: validation approved commands; execution permissions and timeout policy exist.

Exit Conditions: test report, command evidence, output refs, and failure classifications are persisted.

Allowed Operations: discover approved command availability, execute commands, collect results, classify command failures.

Allowed Agents: Test Execution Agent, Validation Agent, Engineering Orchestrator.

Allowed Tools: Testing Tools, System Tools, Validation Tools, Git Read Tools, Audit Tools, State Tools.

Required Memory: test result memory, validation memory, tool invocation memory.

Generated Events: `TestsDiscovered`, `TestsStarted`, `TestsPassed`, `TestsFailed`, `TestsTimedOut`, `CheckpointCreated`.

Failure Conditions: failing tests, command unavailable, dependency failure, timeout, unsafe command request.

Recovery Strategy: retry command only if idempotent and transient; otherwise route to `RETRY` or `ESCALATE`.

Confidence Impact: validation and overall confidence increase on relevant passes and decrease on failures.

Audit Requirements: record command, environment summary, duration, exit code, output refs, truncation, and classification.

Timeout Expectations: medium to long; bounded by command policy.

Retry Eligibility: retryable for transient environment failures; code/test failures require changed strategy.

Success Criteria: required commands complete or are explicitly skipped with accepted rationale.

Next Valid States: `GENERATE_REVIEW`, `RETRY`, `VALIDATE`, `ESCALATE`, `FAILED`, `CANCELLED`.

Invalid Transitions: code modification without recovery decision, `COMPLETED` before review.

### `RETRY`

Purpose: Decide and record a changed recovery strategy after recoverable failure.

Entry Conditions: structured failure exists; retry budget remains; failure is recoverable or diagnosable.

Exit Conditions: retry attempt record, changed strategy, resume state, and confidence adjustments are persisted.

Allowed Operations: classify failure, compare prior strategies, select safe resume state, update retry counters.

Allowed Agents: Retry & Recovery Agent, Engineering Orchestrator, State Management Agent, Audit Logging Agent.

Allowed Tools: State Tools, Audit Tools, Memory Read/Write Tools, read-only diagnostics.

Required Memory: retry attempts, failure reasons, confidence history, decision history.

Generated Events: `RetryStarted`, `RetryStrategySelected`, `RetryCompleted`, `RetryRejected`.

Failure Conditions: budget exhausted, repeated strategy, unsafe side effects, unknown critical failure.

Recovery Strategy: escalate when human decision is useful; fail when platform integrity is unrecoverable.

Confidence Impact: lowers affected confidence fields until new evidence validates the strategy.

Audit Requirements: record failure category, attempt count, changed input/strategy, resume state, and rejected repeats.

Timeout Expectations: short to medium.

Retry Eligibility: not recursively retryable without a distinct meta-failure classification.

Success Criteria: a deterministic resume state and changed strategy exist.

Next Valid States: `COLLECT_CONTEXT`, `SEARCH_REPOSITORY`, `READ_FILES`, `ANALYZE`, `PLAN`, `GENERATE_PATCH`, `APPLY_PATCH`, `VALIDATE`, `RUN_TESTS`, `ESCALATE`, `FAILED`, `CANCELLED`.

Invalid Transitions: `IDLE`, `INITIALIZING`, `COMPLETED`, direct `UNDERSTAND_ISSUE` unless issue reinterpretation is explicitly recorded as the changed strategy.

### `GENERATE_REVIEW`

Purpose: Produce final engineering review, PR description draft, issue response draft, or terminal handoff summary.

Entry Conditions: validation/test outcome supports completion, or escalation/failure requires summary.

Exit Conditions: final review artifact and terminal summary refs are persisted.

Allowed Operations: summarize issue, cause, changes, validation, limitations, residual risk, and changed files.

Allowed Agents: Review Generation Agent, Engineering Orchestrator, Audit Logging Agent, Memory Management Agent for proposed learning.

Allowed Tools: File System Read Tools, Git Diff/Status Tools, Audit Tools, State Tools, Memory Proposal Tools.

Required Memory: review memory, validation memory, test memory, decision history, audit refs.

Generated Events: `ReviewGenerated`, `TerminalSummaryCreated`, `WorkflowReadyToComplete`.

Failure Conditions: missing essential artifacts, unresolved critical risk, review cannot truthfully support terminal state.

Recovery Strategy: return to validation/test or escalate if evidence cannot be completed.

Confidence Impact: finalizes `overall` confidence before terminal transition.

Audit Requirements: record review ref, validation evidence, limitations, and terminal recommendation.

Timeout Expectations: short to medium.

Retry Eligibility: retryable only for missing artifact fetches or formatting defects; not for unresolved engineering risk.

Success Criteria: maintainer-facing review is evidence-backed and complete enough for closure.

Next Valid States: `COMPLETED`, `ESCALATE`, `FAILED`, `CANCELLED`.

Invalid Transitions: engineering modification states unless validation explicitly reopens through `RETRY`.

### `ESCALATE`

Purpose: Convert unsafe uncertainty, missing permission, product ambiguity, or exhausted recovery into a human-actionable packet.

Entry Conditions: escalation trigger exists with evidence and reason.

Exit Conditions: escalation packet, human question/decision request, pause/resume instructions, and audit refs are persisted.

Allowed Operations: classify blocker, prepare decision request, publish authorized notification, suspend workflow.

Allowed Agents: Escalation Agent, Engineering Orchestrator, Review Generation Agent for handoff, Audit Logging Agent.

Allowed Tools: State Tools, Audit Tools, Notification Tools when authorized, Memory Tools for escalation summary.

Required Memory: escalation summary, blocker refs, retry history, evidence refs.

Generated Events: `EscalationStarted`, `WorkflowPaused`, `EscalationPublished`, `WorkflowResumed` after human input.

Failure Conditions: insufficient evidence to ask a useful question, notification failure, missing auditability.

Recovery Strategy: gather minimal evidence if safe; otherwise enter `FAILED` with failure report.

Confidence Impact: marks overall confidence `blocked`, `low`, or `unknown`.

Audit Requirements: record reason, urgency, evidence, human question, notification target, and resume criteria.

Timeout Expectations: short to prepare; wait time is external and represented as suspension, not active execution.

Retry Eligibility: not retryable without new human input or changed permission/access state.

Success Criteria: human can decide next action without reconstructing the workflow.

Next Valid States: `UNDERSTAND_ISSUE`, `CLONE_REPOSITORY`, `COLLECT_CONTEXT`, `SEARCH_REPOSITORY`, `READ_FILES`, `ANALYZE`, `PLAN`, `GENERATE_PATCH`, `APPLY_PATCH`, `VALIDATE`, `RUN_TESTS`, `GENERATE_REVIEW`, `FAILED`, `CANCELLED`.

Invalid Transitions: `COMPLETED` unless review and completion criteria already exist.

### `COMPLETED`

Purpose: Immutable successful terminal state.

Entry Conditions: final review exists; validation state is accepted; terminal audit closure can be recorded.

Exit Conditions: none.

Allowed Operations: read state, archive by policy, propose curated memory updates.

Allowed Agents: State Management Agent, Audit Logging Agent, Memory Management Agent.

Allowed Tools: State Read Tools, Audit Tools, Memory Proposal Tools.

Required Memory: terminal review, validation/test refs, execution timeline, final confidence.

Generated Events: `WorkflowCompleted`, `StateEntered`, `AuditClosed`.

Failure Conditions: terminal closure persistence failure.

Recovery Strategy: recover terminal closure from checkpoint; do not reopen without administrative action.

Confidence Impact: frozen.

Audit Requirements: record terminal state, artifact refs, confidence, limitations, and cleanup status.

Timeout Expectations: short.

Retry Eligibility: not retryable.

Success Criteria: terminal state and audit closure are durable.

Next Valid States: none.

Invalid Transitions: all non-administrative transitions.

### `FAILED`

Purpose: Immutable terminal state for unrecoverable platform, state, tool, policy, or integrity failure.

Entry Conditions: unrecoverable failure is classified and failure report exists or can be produced.

Exit Conditions: none.

Allowed Operations: read state, archive, generate failure diagnostics, propose prevention memory.

Allowed Agents: State Management Agent, Audit Logging Agent, Retry & Recovery Agent, Review Generation Agent.

Allowed Tools: State Read Tools, Audit Tools, Memory Proposal Tools.

Required Memory: failure reason, retry history if any, confidence history, side-effect summary.

Generated Events: `WorkflowFailed`, `StateEntered`, `AuditClosed`.

Failure Conditions: failure report missing or audit closure unavailable.

Recovery Strategy: restore latest valid checkpoint for diagnostic reporting; do not continue engineering work.

Confidence Impact: frozen as failed/blocked.

Audit Requirements: record failure category, recoverability, side effects, skipped cleanup, and evidence refs.

Timeout Expectations: short.

Retry Eligibility: not retryable except administrative replay as a new workflow instance.

Success Criteria: failure is reconstructable from state and audit.

Next Valid States: none.

Invalid Transitions: all non-administrative transitions.

### `CANCELLED`

Purpose: Immutable terminal state for external, user, policy, or administrative cancellation.

Entry Conditions: cancellation request is authorized and safe cancellation obligations are recorded.

Exit Conditions: none.

Allowed Operations: cancel pending work, record side effects, release locks, archive by policy.

Allowed Agents: Engineering Orchestrator, State Management Agent, Audit Logging Agent.

Allowed Tools: State Tools, Audit Tools, safe cancellation hooks owned by runtime tools when implemented.

Required Memory: cancellation request, latest checkpoint, side-effect summary.

Generated Events: `WorkflowCancelled`, `StateEntered`, `AuditClosed`.

Failure Conditions: cancellation authority missing, unknown active side effects, lock release failure.

Recovery Strategy: preserve state as failed if cancellation cannot be made safe; otherwise terminal cancellation.

Confidence Impact: frozen.

Audit Requirements: record actor, reason, point of cancellation, side effects, locks, and cleanup obligations.

Timeout Expectations: short, plus bounded cleanup policy.

Retry Eligibility: not retryable; restarting creates a new workflow.

Success Criteria: workflow stops safely and cannot continue implicitly.

Next Valid States: none.

Invalid Transitions: all non-administrative transitions.

## Transition Graph

Canonical forward path:

```text
IDLE
  -> INITIALIZING
  -> UNDERSTAND_ISSUE
  -> CLONE_REPOSITORY
  -> COLLECT_CONTEXT
  -> SEARCH_REPOSITORY
  -> READ_FILES
  -> ANALYZE
  -> PLAN
  -> GENERATE_PATCH
  -> APPLY_PATCH
  -> VALIDATE
  -> RUN_TESTS
  -> GENERATE_REVIEW
  -> COMPLETED
```

Valid recovery and branch edges:

```text
INITIALIZING -> ESCALATE | FAILED | CANCELLED
UNDERSTAND_ISSUE -> CLONE_REPOSITORY | COLLECT_CONTEXT | ESCALATE | FAILED | CANCELLED
CLONE_REPOSITORY -> COLLECT_CONTEXT | UNDERSTAND_ISSUE | ESCALATE | FAILED | CANCELLED
COLLECT_CONTEXT -> SEARCH_REPOSITORY | READ_FILES | ESCALATE | FAILED | CANCELLED
SEARCH_REPOSITORY -> READ_FILES | COLLECT_CONTEXT | RETRY | ESCALATE | FAILED | CANCELLED
READ_FILES -> ANALYZE | SEARCH_REPOSITORY | COLLECT_CONTEXT | ESCALATE | FAILED | CANCELLED
ANALYZE -> PLAN | READ_FILES | SEARCH_REPOSITORY | RETRY | ESCALATE | FAILED | CANCELLED
PLAN -> GENERATE_PATCH | ANALYZE | READ_FILES | RETRY | ESCALATE | FAILED | CANCELLED
GENERATE_PATCH -> APPLY_PATCH | PLAN | READ_FILES | RETRY | ESCALATE | FAILED | CANCELLED
APPLY_PATCH -> VALIDATE | GENERATE_PATCH | RETRY | ESCALATE | FAILED | CANCELLED
VALIDATE -> RUN_TESTS | GENERATE_PATCH | PLAN | RETRY | ESCALATE | FAILED | CANCELLED
RUN_TESTS -> GENERATE_REVIEW | VALIDATE | RETRY | ESCALATE | FAILED | CANCELLED
RETRY -> COLLECT_CONTEXT | SEARCH_REPOSITORY | READ_FILES | ANALYZE | PLAN | GENERATE_PATCH | APPLY_PATCH | VALIDATE | RUN_TESTS | ESCALATE | FAILED | CANCELLED
GENERATE_REVIEW -> COMPLETED | ESCALATE | FAILED | CANCELLED
ESCALATE -> any non-terminal resume state authorized by human input, or FAILED | CANCELLED
```

Terminal states have no normal outgoing transitions.

## Transition Rules

Every transition must satisfy the transition contract in [states/contracts/transition-contract.yaml](states/contracts/transition-contract.yaml).

Required fields:

- `transition_id`: stable unique transition attempt id.
- `workflow_id`: workflow instance id.
- `from_state`: persisted current state.
- `to_state`: requested target state.
- `trigger`: event, decision, external request, policy, or administrative action.
- `initiator`: actor requesting transition.
- `validator`: State Management Agent or authorized state validator.
- `reason`: bounded human-readable reason.
- `preconditions`: objective checks that must pass.
- `postconditions`: persisted outcomes after success.
- `memory_updates`: objects created, updated, pinned, or invalidated.
- `confidence_updates`: fields changed and evidence.
- `audit_entries`: required audit event refs.
- `event_publication`: lifecycle events emitted.
- `failure_handling`: route on rejection or partial failure.
- `rollback_requirements`: side effects to undo or preserve if transition fails.

Generic transition algorithm:

1. Acquire workflow state lock.
2. Load persisted current state and latest checkpoint.
3. Verify requested `from_state` equals persisted current state.
4. Verify `to_state` is in the legal graph for `from_state`.
5. Validate preconditions, artifact refs, memory refs, locks, permissions, policy, and confidence gates.
6. Emit `TransitionStarted`.
7. Persist transition decision and checkpoint if required.
8. Update current state, confidence snapshot, retry metadata, and memory refs atomically.
9. Emit `StateExited`, `StateEntered`, and `TransitionCompleted`.
10. Release or transfer locks according to the target state.

Failure handling:

- Illegal transition: emit `TransitionRejected`; state remains unchanged.
- Missing artifact: reject and route to the earliest evidence state or `RETRY`.
- Corrupt state: freeze writes, emit `WorkflowRecovered` only after checkpoint restore, otherwise `FAILED`.
- Partial side effects: record cleanup obligations and route to `RETRY`, `ESCALATE`, or `FAILED`.
- Duplicate transition id: return prior result if idempotency key matches; reject if payload differs.

## State Ownership

Who may initiate transitions:

- Engineering Orchestrator may initiate normal lifecycle transitions.
- Retry & Recovery Agent may recommend retry transitions but cannot commit them directly.
- Escalation Agent may recommend pause/resume transitions but cannot commit them directly.
- State Management Agent may initiate recovery transitions after crash or corruption detection.
- Authorized administrator or policy controller may initiate cancellation or emergency failure transitions.

Who validates transitions:

- State Management Agent validates persisted state, legal graph, locks, idempotency, checkpoint integrity, and terminal immutability.
- Engineering Orchestrator validates lifecycle rationale, confidence gates, artifact readiness, and policy fit.
- Audit Logging Agent validates auditability requirements for side-effecting transitions.

Who rejects transitions:

- State Management Agent rejects illegal, duplicate, stale, corrupt, or lock-conflicting transitions.
- Audit Logging Agent can block side-effecting transitions when audit cannot be recorded.
- Policy controller can reject permission, safety, or administrative violations.

Who records transitions:

- State Management Agent records authoritative state changes.
- Audit Logging Agent records audit entries.
- Memory Management Agent records memory objects only through memory contracts.

Who may force transitions:

- Administrative controller may force `CANCELLED` or `FAILED` for emergency shutdown, security incident, policy violation, or unrecoverable corruption.
- Forced transitions must include authority, reason, side-effect summary, and audit refs.

Emergency transitions:

- Any non-terminal state may transition to `CANCELLED` on authorized cancellation when cleanup can be bounded.
- Any non-terminal state may transition to `FAILED` on unrecoverable state, audit, security, or integrity failure.
- Any non-terminal state may transition to `ESCALATE` when human decision is required and state integrity remains trusted.

Administrative transitions:

- Terminal states may be archived, annotated, or superseded by a new workflow instance.
- Terminal states must not resume normal execution.

## State Persistence

State must survive retry, crash, restart, pause, resume, escalation, checkpoint restore, and rollback planning.

Persisted execution state includes:

- workflow id, repository ref, issue ref, workspace ref, and current revision.
- current primary state and active sub-state if any.
- legal transition history with ids and audit refs.
- latest valid checkpoint ref and pinned memory refs.
- artifact refs and versions.
- confidence snapshot and confidence history ref.
- retry count, retry budget ref, failure refs, and rejected strategies.
- locks held, locks released, and cleanup obligations.
- active suspension/resume token for escalation or pause.
- terminal summary ref when terminal.

Retry: persist failure, changed strategy, resume state, and affected confidence fields before leaving `RETRY`.

Crash: restore from latest valid checkpoint, validate repository revision and side effects, then emit `WorkflowRecovered`.

Restart: reload state from durable store, verify graph/schema versions, refresh stale tool/workspace refs, and resume only from a checkpoint-compatible state.

Pause: create checkpoint, record reason, release unsafe locks, emit `WorkflowPaused`.

Resume: validate resume authority, checkpoint freshness, memory refs, repository revision, and human response before transition.

Escalation: persist escalation packet, human question, blocked state, resume criteria, and notification refs.

Checkpoint Restore: pin memory object versions and artifact hashes; mark stale or missing refs before continuing.

Rollback: state records rollback requirements and safe restore points. Actual rollback is performed by future policy/tool implementations, not by this state machine scaffolding.

## State Validation

Integrity checks:

- `workflow_id` exists and matches all artifact/memory/audit refs.
- Current state is a valid enum and exactly one primary state is active.
- Terminal states are immutable.
- Transition history is append-only and ordered.
- Latest transition target equals current state.
- Checkpoint state matches current state or declared restore point.
- Repository revision matches state expectations or is marked stale.
- Locks are owned by the workflow and valid for the operation.
- Confidence fields use allowed values and cite evidence.
- Memory refs exist, are version-pinned, and pass schema compatibility.

Illegal transition detection:

- Reject target not listed in legal graph.
- Reject skipped safety gates such as `APPLY_PATCH` before `GENERATE_PATCH`.
- Reject modification without write lock and approved patch.
- Reject `RUN_TESTS` before validation-selected commands.
- Reject `COMPLETED` without final review and terminal audit.

Missing state detection:

- If current state is absent, restore from latest checkpoint.
- If no valid checkpoint exists, enter `FAILED` with corruption report.
- If transition history conflicts with current state, freeze writes and recover from audit/state consensus.

Duplicate transition detection:

- Use transition id and idempotency key.
- Identical duplicate returns prior accepted/rejected result.
- Non-identical duplicate is rejected and audited.

Recovery after corruption:

- Stop normal transitions.
- Acquire recovery lock.
- Compare state, checkpoint, audit, and memory refs.
- Restore the latest internally consistent snapshot.
- Emit `WorkflowRecovered` with recovery evidence.
- Escalate or fail if side effects cannot be reconstructed.

Validator scaffolding lives in [states/validators/](states/validators/).

## State Events

State events are immutable facts, not commands. Event contracts live in [states/events/lifecycle-events.yaml](states/events/lifecycle-events.yaml).

| Event | Publisher | Subscribers |
| --- | --- | --- |
| `StateEntered` | State Management | Orchestrator, Audit Logging, Observability, Memory |
| `StateExited` | State Management | Orchestrator, Audit Logging, Observability |
| `TransitionStarted` | State Management | Audit Logging, Observability |
| `TransitionCompleted` | State Management | Orchestrator, Audit Logging, Memory |
| `TransitionRejected` | State Management | Orchestrator, Retry & Recovery, Audit Logging |
| `TransitionRolledBack` | State Management | Orchestrator, Audit Logging, Retry & Recovery |
| `WorkflowPaused` | Orchestrator / State Management | Escalation, Audit Logging, Observability |
| `WorkflowResumed` | State Management | Orchestrator, Audit Logging, Memory |
| `WorkflowCancelled` | State Management | Orchestrator, Audit Logging, Runtime |
| `WorkflowRecovered` | State Management | Orchestrator, Audit Logging, Retry & Recovery |
| `WorkflowCompleted` | State Management | Audit Logging, Memory Management, Review |
| `WorkflowFailed` | State Management | Audit Logging, Retry & Recovery, Review |

## Nested States

Nested states are appropriate only inside primary states where internal progress must be observable and resumable but should not expand the global transition graph.

Rules:

- A nested state cannot exist without its parent primary state.
- Nested state transitions must not bypass primary state transitions.
- Nested states must be persisted if their work is long-running or side-effecting.
- Nested states emit events with both `primary_state` and `sub_state`.
- Nested failure routes through the parent state's exits.

Recommended nested states:

`RUN_TESTS`:

```text
DISCOVER_TESTS -> EXECUTE_TESTS -> COLLECT_RESULTS -> ANALYZE_RESULTS -> PUBLISH_OUTCOME
```

`APPLY_PATCH`:

```text
ACQUIRE_WRITE_LOCK -> VERIFY_BASELINE -> APPLY_EDITS -> INSPECT_DIFF -> PUBLISH_CHANGE_MANIFEST -> RELEASE_OR_TRANSFER_LOCK
```

`ESCALATE`:

```text
CLASSIFY_BLOCKER -> BUILD_PACKET -> PUBLISH_REQUEST -> WAIT_FOR_RESPONSE -> RESUME_OR_TERMINATE
```

Nested states are not necessary for short, read-only states such as `SEARCH_REPOSITORY` unless searches become asynchronous and checkpointed.

Nested state templates live in [states/definitions/nested-states.yaml](states/definitions/nested-states.yaml).

## State Contracts

Every future execution state must use the reusable contract in [states/contracts/state-contract.yaml](states/contracts/state-contract.yaml).

Required sections:

- identity and version.
- purpose and ownership.
- entry and exit conditions.
- allowed operations, agents, and tools.
- required memory and generated memory.
- generated events and audit requirements.
- failure conditions and recovery strategy.
- confidence impact.
- timeout expectations.
- retry eligibility.
- success criteria.
- next valid states and invalid transitions.
- persistence and checkpoint requirements.
- extension and compatibility notes.

## Best Practices

- Keep state definitions declarative and stable.
- Add new states only when lifecycle position, permissions, recovery, or audit meaning changes.
- Prefer nested states for internal progress within a primary state.
- Never encode business logic or prompts in state definitions.
- Make entry and exit criteria objective.
- Keep recovery routes explicit and bounded.
- Treat confidence changes as state-relevant evidence, not decoration.
- Use artifact refs rather than copying large outputs into state.
- Preserve terminal immutability.
- Version state definitions and migration expectations.

## Extension Guide

To add a state:

1. Confirm an existing state or nested state cannot represent the lifecycle position.
2. Create a state definition under `states/definitions/`.
3. Add legal transitions under `states/transitions/`.
4. Define events under `states/events/` if new lifecycle facts are needed.
5. Add validation rules under `states/validators/`.
6. Update configuration defaults under `states/configuration/`.
7. Declare interfaces impacted under `states/interfaces/`.
8. Update this `STATES.md` catalog and any relevant docs/specifications.
9. Ensure no runtime execution or business logic is introduced in the contract.

## Supporting Specifications

- [states/README.md](states/README.md)
- [states/definitions/primary-states.yaml](states/definitions/primary-states.yaml)
- [states/definitions/nested-states.yaml](states/definitions/nested-states.yaml)
- [states/contracts/state-contract.yaml](states/contracts/state-contract.yaml)
- [states/contracts/transition-contract.yaml](states/contracts/transition-contract.yaml)
- [states/contracts/checkpoint-contract.yaml](states/contracts/checkpoint-contract.yaml)
- [states/transitions/transition-graph.yaml](states/transitions/transition-graph.yaml)
- [states/transitions/transition-rules.yaml](states/transitions/transition-rules.yaml)
- [states/validators/state-integrity-rules.yaml](states/validators/state-integrity-rules.yaml)
- [states/events/lifecycle-events.yaml](states/events/lifecycle-events.yaml)
- [states/configuration/state-machine.defaults.yaml](states/configuration/state-machine.defaults.yaml)
- [states/interfaces/state-store.interface.yaml](states/interfaces/state-store.interface.yaml)
- [states/interfaces/state-transition.interface.yaml](states/interfaces/state-transition.interface.yaml)
