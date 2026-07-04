# GitHub Engineering Worker Agent Architecture

GitHub Engineering Worker is an autonomous OpenClaw-based software engineering platform. It owns the complete lifecycle of a GitHub Issue from intake through repository understanding, implementation planning, validation, recovery, escalation, and engineering review.

This file is the canonical agent architecture contract. It is intentionally declarative: it defines agent responsibilities, communication boundaries, lifecycle expectations, confidence standards, and extension rules. It does not implement tools, workflows, retries, memory, state machines, or prompts.

## Design Philosophy

The platform is modeled as a small engineering organization, not a single general-purpose prompt. Each agent has a bounded role, explicit inputs and outputs, narrow tool permissions, and clear success criteria. The Engineering Orchestrator coordinates the work, but it does not perform engineering tasks directly.

Core principles:

- Separation of responsibilities: each agent owns one durable capability.
- Explicit communication: agents exchange structured artifacts, not informal transcript fragments.
- Loose coupling: agents depend on contracts and artifacts, not each other's internals.
- Evidence-first work: conclusions must cite repository, issue, test, or tool evidence.
- Minimal context movement: agents receive only the information needed for their task.
- Human escalation by design: uncertainty, safety risk, missing permissions, and ambiguous product intent are valid outcomes.
- Auditable autonomy: material decisions and side effects must be recordable and reviewable.

## Agent Hierarchy

The hierarchy is coordinative, not managerial in the human sense:

- Engineering Orchestrator Agent
  - Issue Understanding Agent
  - Repository Context Agent
  - Repository Search Agent
  - File Reader Agent
  - Root Cause Analysis Agent
  - Planning Agent
  - Patch Generation Agent
  - Code Modification Agent
  - Validation Agent
  - Test Execution Agent
  - Retry & Recovery Agent
  - Review Generation Agent
  - Escalation Agent
  - Audit Logging Agent
  - Memory Management Agent
  - State Management Agent

Optional extension agents may be introduced for specialized domains such as security analysis, dependency analysis, database migration review, API compatibility review, documentation review, release readiness, or performance profiling. Extension agents must follow the same contract model and must not absorb orchestration responsibility.

## Shared Workflow Model

The system follows an Observe -> Think -> Plan -> Execute -> Validate -> Learn -> Decide loop:

1. Observe: gather issue, repository, state, memory, and execution context.
2. Think: understand intent, constraints, likely ownership, and risk.
3. Plan: produce a bounded implementation plan and validation strategy.
4. Execute: generate and apply narrowly scoped changes.
5. Validate: run tests, inspect diffs, and verify acceptance criteria.
6. Learn: record reusable findings, failures, and recovery knowledge.
7. Decide: finish, retry, gather more information, or escalate.

Only the orchestrator chooses transitions between phases. Specialist agents produce artifacts and confidence assessments for the orchestrator to evaluate.

## Communication Model

Agents communicate through structured messages and shared artifacts. They do not rely on hidden conversational state.

### Message Envelope

Every agent request and response should conform to this conceptual envelope:

```yaml
message_id: stable unique id
correlation_id: issue/workflow id shared across the lifecycle
sender: agent identity
recipient: target agent identity
message_type: request | response | event | escalation | audit
intent: concise purpose of the message
inputs: references to required artifacts or inline bounded data
constraints: time, scope, policy, safety, or tool limits
required_output: expected artifact type and acceptance criteria
confidence_required: minimum confidence threshold if applicable
trace_refs: related state, audit, memory, log, or tool references
created_at: timestamp
```

Responses should include:

```yaml
status: success | partial | failed | blocked | escalated
outputs: produced artifact references or bounded inline data
evidence: repository paths, issue refs, command refs, test refs, or reasoning summaries
confidence: numeric or categorical confidence with justification
risks: known gaps, assumptions, or hazards
next_recommended_action: optional recommendation to the orchestrator
audit_events: material decisions or side effects to record
```

### Request/Response Interactions

Request/response is used when one agent needs a bounded artifact from another agent. Examples:

- Orchestrator -> Issue Understanding: produce issue intent and acceptance criteria.
- Root Cause Analysis -> File Reader: read specific files with exact line targets.
- Planning -> Validation: assess proposed validation strategy.

The requesting agent must state the exact output required. The responding agent must avoid doing adjacent work outside its contract.

### Event-Based Interactions

Events are used for lifecycle and observability:

- issue.accepted
- context.collected
- plan.proposed
- patch.generated
- patch.applied
- validation.failed
- retry.started
- escalation.requested
- review.completed

Events are immutable facts. They are consumed by the orchestrator, audit logging, state management, and memory management as appropriate.

### Shared Context

Shared context is artifact-based:

- Issue brief
- Repository map
- Search results
- File excerpts
- Root cause report
- Implementation plan
- Patch proposal
- Applied change manifest
- Validation report
- Test execution report
- Retry report
- Escalation packet
- Final engineering review

Agents should pass artifact identifiers whenever possible instead of copying entire content. Large repository files, logs, and test outputs should be summarized with pointers to full evidence.

### Synchronization Strategy

The State Management Agent owns workflow state, locks, checkpoints, and resumability metadata. The orchestrator uses state to prevent conflicting work and to resume after interruption. Specialist agents may read state relevant to their task but must not bypass the orchestrator to mutate lifecycle state.

### Avoiding Unnecessary Communication

Communication is avoided by:

- Assigning each artifact a single owner.
- Returning confidence and known gaps with every response.
- Using file excerpts instead of whole repositories.
- Using search results before file reads.
- Reusing validated artifacts until repository state changes.
- Letting the orchestrator decide when more evidence is needed.

## Engineering Orchestrator Agent

Identity: Engineering Orchestrator Agent

Purpose: Own the complete issue lifecycle and coordinate specialist agents without performing their work.

Responsibilities:

- Accept a repository and GitHub Issue reference.
- Initialize workflow state and correlation identifiers.
- Select the next agent based on current state, confidence, risk, and blockers.
- Determine when enough information has been collected.
- Maintain high-level confidence for issue understanding, root cause, plan quality, implementation readiness, and validation readiness.
- Enforce phase boundaries and tool permission boundaries.
- Decide whether to continue, retry, recover, escalate, or terminate.
- Ensure all material decisions are auditable.
- Terminate safely with a final review, escalation packet, or failure report.

Inputs:

- Repository identifier and access context.
- GitHub Issue identifier or issue payload.
- Runtime policy and configuration.
- Current workflow state.
- Relevant memory and prior attempt summaries.

Outputs:

- Lifecycle decisions.
- Agent task requests.
- State transition requests.
- Retry decisions.
- Escalation decisions.
- Final completion decision.

Internal reasoning responsibilities:

- Compare specialist outputs against acceptance criteria.
- Detect missing evidence, circular reasoning, or premature implementation.
- Balance additional context gathering against cost and diminishing returns.
- Identify when confidence is insufficient for autonomous modification.
- Ensure retry attempts change strategy rather than repeat failure.

Information required:

- Current issue brief.
- Repository context summary.
- Evidence inventory.
- Agent confidence reports.
- Validation status.
- Retry history.
- Policy constraints.

Information produced:

- Decision log entries.
- Current phase and next action.
- Confidence rollups.
- Stop conditions.
- Escalation rationale when needed.

Communicates with:

- All agents.

Tools it may invoke:

- State management interface.
- Audit logging interface.
- Agent dispatch interface.
- Memory retrieval interface.
- Escalation interface.

Success criteria:

- The issue lifecycle reaches a safe terminal state.
- All engineering work is delegated to specialist agents.
- Decisions are evidence-backed and auditable.
- No unnecessary repository-wide context is gathered.
- Failed attempts are retried only with a changed hypothesis or strategy.

Failure conditions:

- Cannot establish issue intent.
- Repository access is unavailable.
- Required tools are unavailable.
- Specialist outputs conflict and cannot be reconciled.
- Validation cannot be completed and risk is too high to proceed.

Confidence expectations:

- Must maintain explicit confidence per phase.
- Must not authorize code modification unless plan confidence and root cause confidence meet configured thresholds.
- Must escalate when confidence remains below threshold after bounded recovery.

Escalation behavior:

- Produce an escalation packet with issue summary, evidence, attempted actions, blockers, risk, and recommended human decision.

## Agent Contracts

The following contracts are mandatory for production agents.

### Issue Understanding Agent

Purpose: Convert raw issue data into a precise engineering brief.

Responsibilities:

- Parse issue title, body, labels, comments, linked PRs, stack traces, screenshots, and reproduction notes.
- Identify user-visible problem, expected behavior, constraints, and acceptance criteria.
- Distinguish explicit requirements from assumptions.
- Flag ambiguity, missing reproduction steps, and product decisions.

Inputs: issue payload, repository metadata, linked discussion references.

Outputs: issue brief, acceptance criteria, ambiguity list, information requests.

Internal reasoning responsibilities: infer likely intent only when evidence supports it; classify ambiguity by severity.

Information required: issue content, labels, milestone, author comments, recent maintainer guidance if available.

Information produced: normalized problem statement, constraints, acceptance criteria, confidence score.

Communicates with: Orchestrator, Repository Context, Escalation, Audit Logging.

Tools it may invoke: GitHub issue read APIs, markdown extraction, attachment metadata readers.

Success criteria: the orchestrator has a bounded, testable description of the issue.

Failure conditions: issue is inaccessible, empty, contradictory, or requires human product judgment.

Confidence expectations: high confidence requires explicit acceptance criteria or reproducible symptoms.

Escalation behavior: request human clarification when acceptance criteria cannot be inferred safely.

### Repository Context Agent

Purpose: Build a concise structural map of the repository relevant to the issue.

Responsibilities:

- Identify languages, frameworks, package managers, test systems, build systems, and repository conventions.
- Locate likely ownership areas without reading unnecessary files.
- Summarize project architecture at the level needed for the issue.
- Report existing documentation or contribution guidance that constrains changes.

Inputs: repository metadata, issue brief, file tree, manifest files, project docs.

Outputs: repository context summary, likely directories, build/test entry points, convention notes.

Internal reasoning responsibilities: map issue concepts to repository areas and distinguish likely from confirmed relevance.

Information required: file tree, README, contribution docs, manifests, workspace configuration.

Information produced: context map, candidate modules, test command candidates, risk notes.

Communicates with: Orchestrator, Repository Search, Planning, Validation.

Tools it may invoke: repository tree listing, manifest readers, documentation readers.

Success criteria: downstream agents know where to search and how the project is organized.

Failure conditions: repository structure is unreadable, unsupported, or too large without index support.

Confidence expectations: confidence should separate repository topology confidence from issue relevance confidence.

Escalation behavior: escalate when repository cannot be classified enough to continue.

### Repository Search Agent

Purpose: Find candidate files, symbols, tests, and documentation relevant to the issue.

Responsibilities:

- Generate targeted search queries from the issue brief and repository context.
- Search symbols, strings, filenames, tests, configuration, and documentation.
- Rank results by likely relevance.
- Avoid broad searches once high-quality candidates are found.

Inputs: issue brief, repository context summary, search constraints.

Outputs: ranked search results, query log, relevance rationale, gaps.

Internal reasoning responsibilities: adapt search terms based on domain vocabulary and avoid confirmation bias.

Information required: repository index or search tooling, candidate directories, ignored paths.

Information produced: ranked file/symbol/test candidates and evidence snippets.

Communicates with: Orchestrator, File Reader, Root Cause Analysis, Audit Logging.

Tools it may invoke: text search, symbol search, file listing, code index search.

Success criteria: identifies the smallest useful set of files to read next.

Failure conditions: search unavailable, results too noisy, no plausible candidates found.

Confidence expectations: high confidence requires multiple converging signals or exact issue terminology matches.

Escalation behavior: recommend broader context gathering or human help if no candidate area emerges.

### File Reader Agent

Purpose: Read and summarize only the files or line ranges required by downstream reasoning.

Responsibilities:

- Retrieve requested files or bounded excerpts.
- Preserve exact paths, line ranges, and relevant code structure.
- Summarize behavior without modifying files.
- Identify imports, call sites, tests, and adjacent files that may need reading.

Inputs: file paths, line ranges, reason for read, context budget.

Outputs: file excerpts, summaries, dependency pointers, read coverage manifest.

Internal reasoning responsibilities: decide whether requested excerpts are sufficient for the stated question.

Information required: repository contents and requested read scope.

Information produced: evidence-grade excerpts and concise summaries.

Communicates with: Orchestrator, Repository Search, Root Cause Analysis, Planning, Patch Generation.

Tools it may invoke: file read tools, syntax-aware readers, dependency graph readers.

Success criteria: downstream agents receive enough evidence without loading unrelated code.

Failure conditions: file missing, generated/binary/unreadable content, requested range insufficient.

Confidence expectations: confidence is high only when relevant control flow and dependencies are covered.

Escalation behavior: report unavailable or unsafe files to the orchestrator.

### Root Cause Analysis Agent

Purpose: Explain why the issue occurs and identify the minimal behavioral change needed.

Responsibilities:

- Analyze issue brief, repository context, search results, and file excerpts.
- Form hypotheses and test them against evidence.
- Identify affected code paths and failure mechanism.
- State what should change and what should not change.

Inputs: issue brief, file excerpts, search results, relevant tests/docs.

Outputs: root cause report, evidence map, affected surface area, confidence score.

Internal reasoning responsibilities: distinguish confirmed root cause from plausible hypothesis; identify missing evidence.

Information required: relevant implementation code, tests, config, runtime assumptions.

Information produced: causal explanation and change target recommendation.

Communicates with: Orchestrator, File Reader, Planning, Validation, Retry & Recovery.

Tools it may invoke: static analysis, dependency inspection, read-only diagnostics.

Success criteria: produces a specific, evidence-backed cause and change target.

Failure conditions: insufficient evidence, multiple incompatible causes, issue not reproducible in code.

Confidence expectations: high confidence requires direct evidence connecting symptom to code path.

Escalation behavior: escalate when product behavior is undefined or cause cannot be isolated safely.

### Planning Agent

Purpose: Produce a bounded implementation and validation plan.

Responsibilities:

- Translate root cause into concrete change steps.
- Define files likely to change and files that must remain untouched.
- Select validation strategy and expected tests.
- Identify rollback, compatibility, and risk considerations.

Inputs: issue brief, root cause report, repository context, relevant file summaries.

Outputs: implementation plan, validation plan, risk assessment, acceptance mapping.

Internal reasoning responsibilities: minimize blast radius and align plan with repository conventions.

Information required: root cause, project conventions, affected files, test commands.

Information produced: ordered plan and validation checklist.

Communicates with: Orchestrator, Patch Generation, Validation, Test Execution, Escalation.

Tools it may invoke: read-only planning aids, dependency graph inspection.

Success criteria: plan is specific enough for patch generation and validation.

Failure conditions: plan requires unsupported tools, unclear acceptance criteria, or risky architecture change.

Confidence expectations: high confidence requires clear root cause and feasible validation path.

Escalation behavior: escalate architectural or product decisions outside issue scope.

### Patch Generation Agent

Purpose: Design the intended code changes as a patch proposal without applying them.

Responsibilities:

- Generate a minimal patch plan aligned with the implementation plan.
- Identify exact files, functions, tests, and documentation to modify.
- Preserve existing style and ownership boundaries.
- Explain expected behavioral impact.

Inputs: implementation plan, relevant file excerpts, conventions, acceptance criteria.

Outputs: patch proposal, change manifest, test additions/updates, rationale.

Internal reasoning responsibilities: ensure proposed changes address the root cause and avoid unrelated refactors.

Information required: target file excerpts, style conventions, test patterns.

Information produced: precise modification intent for Code Modification.

Communicates with: Orchestrator, File Reader, Code Modification, Validation.

Tools it may invoke: diff planning, static syntax inspection, formatting guidance readers.

Success criteria: Code Modification can apply changes without redoing design work.

Failure conditions: insufficient file context, conflicting style patterns, patch would exceed scope.

Confidence expectations: high confidence requires clear edit locations and expected test impact.

Escalation behavior: return to orchestrator for more file context or human review of broad changes.

### Code Modification Agent

Purpose: Apply approved code changes to the repository.

Responsibilities:

- Modify only files authorized by the orchestrator and patch proposal.
- Preserve formatting and local conventions.
- Produce an applied change manifest and diff summary.
- Refuse changes outside scope.

Inputs: approved patch proposal, target files, modification constraints.

Outputs: applied changes, diff summary, changed-file manifest, modification confidence.

Internal reasoning responsibilities: handle local edit mechanics while preserving intent.

Information required: current file contents, approved change manifest, repository write permissions.

Information produced: concrete diff and changed files.

Communicates with: Orchestrator, Patch Generation, Validation, Audit Logging, State Management.

Tools it may invoke: file edit tools, formatter tools when approved, diff tools.

Success criteria: intended changes are applied cleanly and narrowly.

Failure conditions: patch conflicts, dirty files outside scope, generated files, permission failures.

Confidence expectations: high confidence requires diff matches patch intent and no unexpected files changed.

Escalation behavior: stop and report when local state conflicts with safe application.

### Validation Agent

Purpose: Evaluate whether applied changes satisfy the issue and repository quality expectations.

Responsibilities:

- Inspect diffs for scope, correctness, style, and acceptance criteria alignment.
- Decide which tests or checks should run.
- Analyze validation evidence from Test Execution.
- Identify residual risks and missing coverage.

Inputs: issue brief, implementation plan, diff summary, test reports.

Outputs: validation report, pass/fail decision, residual risk list, next action recommendation.

Internal reasoning responsibilities: connect evidence to acceptance criteria and detect false confidence.

Information required: diff, plan, tests, command outputs, known project quality gates.

Information produced: validation decision and evidence map.

Communicates with: Orchestrator, Test Execution, Retry & Recovery, Review Generation.

Tools it may invoke: diff inspection, static analysis readers, quality gate readers.

Success criteria: produces a defensible validation decision.

Failure conditions: validation evidence unavailable, tests inconclusive, diff exceeds understood scope.

Confidence expectations: high confidence requires relevant tests or strong static/manual evidence.

Escalation behavior: escalate when validation cannot establish safety for the change.

### Test Execution Agent

Purpose: Run approved tests and checks, then report factual results.

Responsibilities:

- Execute only commands authorized by the orchestrator or validation plan.
- Capture command, environment, exit code, duration, and relevant output.
- Classify failures as test failure, environment failure, timeout, dependency failure, or command error.
- Avoid interpreting product correctness beyond test evidence.

Inputs: validation plan, command list, timeout/resource policy, repository state.

Outputs: test execution report, command evidence, failure classification.

Internal reasoning responsibilities: determine whether command execution completed reliably.

Information required: test commands, environment constraints, repository working directory.

Information produced: factual test results and output summaries.

Communicates with: Orchestrator, Validation, Retry & Recovery, Audit Logging.

Tools it may invoke: shell/CI test execution, environment inspection, log capture.

Success criteria: commands run as requested and results are reproducible from the report.

Failure conditions: command unavailable, dependency missing, timeout, flaky behavior, unsafe command.

Confidence expectations: high confidence requires successful command completion with clear exit status.

Escalation behavior: report blocked test execution with remediation suggestions.

### Retry & Recovery Agent

Purpose: Diagnose failed attempts and propose a changed recovery strategy.

Responsibilities:

- Analyze validation failures, test failures, patch conflicts, and missing-context failures.
- Determine whether retry is appropriate.
- Propose a different hypothesis, additional context request, patch adjustment, or escalation.
- Track retry limits and avoid repeated identical attempts.

Inputs: failure reports, retry history, state snapshot, evidence artifacts.

Outputs: recovery recommendation, retry classification, modified strategy, escalation recommendation.

Internal reasoning responsibilities: separate implementation mistakes from incorrect root cause or environmental failures.

Information required: prior plans, diffs, test outputs, failure classifications, attempt count.

Information produced: changed recovery strategy and confidence.

Communicates with: Orchestrator, Root Cause Analysis, Planning, Patch Generation, Validation, Escalation.

Tools it may invoke: read-only diagnostics, diff inspection, log analysis.

Success criteria: each retry has a materially improved strategy or escalation is recommended.

Failure conditions: repeated failures, unsafe uncertainty, exhausted retry budget.

Confidence expectations: high confidence requires a specific explanation of the failure and changed action.

Escalation behavior: escalate after bounded retries or when recovery requires human judgment.

### Review Generation Agent

Purpose: Produce the final professional engineering review for maintainers.

Responsibilities:

- Summarize the issue, root cause, changes, validation, and residual risks.
- Include changed files and test evidence.
- Mention limitations honestly.
- Produce human-readable output suitable for a PR, issue comment, or engineering handoff.

Inputs: issue brief, root cause report, diff summary, validation report, test report, audit highlights.

Outputs: final engineering review, PR description draft, issue response draft if applicable.

Internal reasoning responsibilities: synthesize evidence without inventing unsupported claims.

Information required: final artifacts and terminal state.

Information produced: concise maintainer-facing review.

Communicates with: Orchestrator, Validation, Audit Logging, Escalation.

Tools it may invoke: artifact readers, diff summary readers.

Success criteria: a maintainer can understand what changed, why, and how it was validated.

Failure conditions: missing validation evidence, inconsistent artifacts, unresolved critical risk.

Confidence expectations: confidence should reflect completeness of evidence, not polish of prose.

Escalation behavior: produce handoff review when the lifecycle ends in escalation instead of completion.

### Escalation Agent

Purpose: Convert blockers and unsafe uncertainty into actionable human escalation.

Responsibilities:

- Classify escalation reason and urgency.
- Prepare minimal human questions or decision requests.
- Include evidence, attempted actions, impact, and recommended options.
- Avoid asking questions already answerable from artifacts.

Inputs: blocker reports, confidence reports, policy constraints, retry history.

Outputs: escalation packet, human question, recommended next steps.

Internal reasoning responsibilities: determine the smallest human decision needed to unblock work.

Information required: issue brief, evidence, current state, failure reports.

Information produced: escalation summary and decision request.

Communicates with: Orchestrator, Issue Understanding, Planning, Retry & Recovery, Review Generation.

Tools it may invoke: notification or review handoff tools when authorized.

Success criteria: a human can make the required decision without reconstructing the full workflow.

Failure conditions: insufficient evidence to frame a useful escalation.

Confidence expectations: high confidence means the escalation reason is specific and well-supported.

Escalation behavior: this agent is the escalation boundary; it does not continue engineering work.

### Audit Logging Agent

Purpose: Record material actions, decisions, evidence references, and side effects.

Responsibilities:

- Capture lifecycle events, decisions, tool invocations, state transitions, and terminal outcomes.
- Preserve correlation between issue, artifacts, commands, and changes.
- Keep audit records factual and tamper-evident where supported.
- Exclude secrets and unnecessary private content.

Inputs: audit events from all agents, tool metadata, state transitions.

Outputs: audit log entries, decision records, evidence index.

Internal reasoning responsibilities: classify audit significance and redact sensitive material.

Information required: event envelopes, artifact references, policy rules.

Information produced: immutable audit trail references.

Communicates with: all agents, especially Orchestrator and State Management.

Tools it may invoke: audit appenders, log storage, redaction helpers.

Success criteria: lifecycle can be reconstructed from audit records.

Failure conditions: audit sink unavailable, redaction uncertainty, inconsistent correlation ids.

Confidence expectations: high confidence requires complete event metadata and safe redaction.

Escalation behavior: block unsafe external actions if auditability cannot be established.

### Memory Management Agent

Purpose: Manage reusable learning without storing raw workflow state or secrets.

Responsibilities:

- Retrieve relevant prior lessons, repository conventions, and historical failure patterns.
- Propose durable memories after completion.
- Avoid storing sensitive data, credentials, or full private code unnecessarily.
- Separate reusable learning from per-run logs.

Inputs: memory queries, terminal workflow summaries, learning candidates.

Outputs: memory retrieval summaries, memory update proposals, retention warnings.

Internal reasoning responsibilities: decide what is generalizable and safe to retain.

Information required: memory policy, current issue summary, prior memory index.

Information produced: bounded memory context and learning recommendations.

Communicates with: Orchestrator, Planning, Retry & Recovery, Review Generation, Audit Logging.

Tools it may invoke: memory search, memory read, memory proposal/update tools.

Success criteria: useful prior knowledge is available without polluting memory with run noise.

Failure conditions: memory unavailable, unsafe retention risk, conflicting memories.

Confidence expectations: memory relevance must be explicit and evidence-linked.

Escalation behavior: ask for human approval before retaining sensitive or ambiguous information.

### State Management Agent

Purpose: Own workflow state, resumability, locks, checkpoints, and terminal status.

Responsibilities:

- Initialize issue workflow state.
- Record current phase, active agent, artifacts, checkpoints, retries, and terminal outcome.
- Enforce locks to prevent conflicting modifications.
- Support suspension and resumption.
- Provide state snapshots to authorized agents.

Inputs: orchestrator state transition requests, agent status events, artifact references.

Outputs: state records, snapshots, lock status, checkpoint references.

Internal reasoning responsibilities: validate legal state transitions and detect stale or conflicting updates.

Information required: workflow id, current state, transition policy, lock policy.

Information produced: authoritative lifecycle state.

Communicates with: Orchestrator, Audit Logging, Code Modification, Test Execution, Retry & Recovery.

Tools it may invoke: state store, lock manager, checkpoint store.

Success criteria: workflow can be paused, resumed, audited, and safely terminated.

Failure conditions: state store unavailable, lock conflict, illegal transition, checkpoint corruption.

Confidence expectations: high confidence requires durable write confirmation.

Escalation behavior: halt workflow on unrecoverable state inconsistency.

## Lifecycle

### Initialization

The orchestrator creates a workflow correlation id, asks State Management to initialize state, asks Audit Logging to begin an audit trail, and retrieves relevant memory. Specialist agents are initialized lazily when their artifact is needed.

### Execution

An agent executes only after receiving an explicit request with inputs, constraints, and expected output. Agents return artifacts and confidence; they do not decide global workflow transitions.

### Suspension

The orchestrator may suspend work when waiting on human input, external systems, long-running checks, rate limits, or unavailable dependencies. State Management records the checkpoint. Audit Logging records the suspension reason.

### Resumption

On resume, the orchestrator reloads state, validates repository and artifact freshness, checks whether assumptions remain true, and continues from the last safe checkpoint. Agents must not assume their previous local context is still current.

### Termination

Terminal states include:

- completed: changes applied and validation passed or was accepted with disclosed limitations.
- escalated: human input is required before safe continuation.
- failed: unrecoverable system/tool/state failure.
- cancelled: external cancellation.

Termination must include final state, audit closure, and either an engineering review or escalation packet.

## Orchestration Strategy

The orchestrator should follow this high-level decision sequence:

1. Create state and audit context.
2. Request issue understanding.
3. Request repository context.
4. Request targeted search.
5. Request file reads for high-ranking candidates.
6. Request root cause analysis.
7. If confidence is low, gather more evidence or escalate.
8. Request implementation and validation plan.
9. Request patch proposal.
10. Authorize code modification only when scope and confidence are acceptable.
11. Request validation analysis and test execution.
12. If validation fails, request retry and recovery.
13. If recovery is justified, loop with changed strategy.
14. If complete, request final review.
15. Close audit and state.

The orchestrator should not skip directly from issue understanding to code modification. It may compress phases only when artifacts already exist and are fresh.

## Extension Guidelines

New agents must:

- Own a distinct responsibility not covered by existing agents.
- Declare inputs, outputs, dependencies, tool permissions, memory access, state access, failure behavior, retry policy, confidence reporting, and audit requirements.
- Produce artifacts consumable by the orchestrator.
- Avoid direct lifecycle transitions.
- Avoid broad repository reads unless that is their explicit contract.
- Emit evidence and confidence with every result.

New tools must be introduced through tool contracts and policy bindings, not by embedding tool behavior in agent descriptions.

New workflows must be declarative and must not hardcode prompts or implementation logic in architecture documents.

## Best Practices

- Prefer exact file paths, line references, commands, and artifact ids over prose-only evidence.
- Keep issue intent, root cause, plan, patch, validation, and review as separate artifacts.
- Treat failed tests as evidence, not merely obstacles.
- Escalate early for product ambiguity and late for engineering uncertainty only after bounded evidence gathering.
- Never let an agent both approve and apply its own changes.
- Never let retry repeat the same failed strategy without new evidence.
- Keep memory curated; keep audit complete.
