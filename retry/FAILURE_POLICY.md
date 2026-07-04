# Failure Policy

The Failure Policy defines how GitHub Engineering Worker classifies failures and routes them to recovery, retry, escalation, or terminal failure. It extends the Tool Framework failure model in [TOOLS.md](../TOOLS.md) and the tool-specific failure shape in [docs/specifications/tool-failures.md](../docs/specifications/tool-failures.md).

## Recoverability Classes

- `retryable`: safe to retry after backoff, refresh, or transient dependency recovery.
- `retry_with_changes`: safe only after changed input, scope, evidence, tool, agent, prompt, patch, or validation strategy.
- `not_retryable`: repeating would not improve the result or would increase risk.
- `escalate`: human, operator, permission, product, or safety decision is required.
- `terminal`: workflow must fail because integrity cannot be restored autonomously.

## Failure Taxonomy

| Failure Type | Description | Severity | Recoverability | Retry Eligibility | Max Retries | Escalation Trigger | Recommended Recovery Strategy | Audit Requirements | Confidence Impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Repository Clone Failure | Repository cannot be cloned, fetched, or materialized. | error | retryable or escalate | Retry only if network/auth/transient cause is likely. | 2 | auth failure, missing repo, repeated clone failure | refresh credentials scope, retry fetch, use alternate mirror if policy allows | repo ref, command/tool ref, auth class, error class | repository_context decreases to low |
| Repository Search Failure | Search index or text search fails. | warning/error | retry_with_changes | Retry with narrower query, alternate search tool, or refreshed index. | 2 | no alternate search and evidence cannot be gathered | re-index, alternate tool, file tree search, collect manifests | query, scope, tool id, result count, failure | root_cause readiness decreases |
| Missing Files | Required path is absent, renamed, generated, ignored, or inaccessible. | warning/error | retry_with_changes | Retry only after refreshed tree, corrected path, or alternate evidence source. | 2 | required file absent after repository refresh | rerun search, inspect manifests, read adjacent references | path, expected source, repo revision, search refs | affected evidence confidence decreases |
| Repository Permission Failure | Repository, file, branch, or operation is denied. | error/critical | escalate | No autonomous retry without permission change. | 0 | required permission missing | escalate for access approval or reduced scope | denied permission, scope, subject, operation | overall confidence blocked |
| Tool Failure | Tool invocation fails structurally or operationally. | warning/error | retryable or retry_with_changes | Retry if idempotent and side effects are known safe. | 2 | repeated crash, unsafe side effects, no alternate tool | select alternate tool, narrow input, refresh state | tool id/version, input hash, side effects, failure | confidence in tool evidence decreases |
| Patch Generation Failure | Patch proposal cannot be produced or is incomplete. | warning/error | retry_with_changes | Retry after more file context, clearer plan, or changed prompt strategy. | 2 | ambiguous edit target persists | read more context, revise plan, improve constraints | plan ref, missing context, attempted files | patch confidence decreases |
| Patch Application Failure | Approved patch cannot be applied cleanly. | error | retry_with_changes | Retry only after base refresh, conflict analysis, or regenerated patch. | 2 | dirty state unsafe, repeated conflict, unauthorized files | restore checkpoint, refresh base hashes, regenerate patch | patch ref, base hash, conflict paths, dirty state | patch and repository safety decrease |
| Compilation Failure | Compiler or type checker fails. | error | retry_with_changes | Retry through patch, plan, or root-cause correction. | 2 | unrelated widespread failures or unknown compiler state | inspect diagnostics, update patch, run targeted checks | command, diagnostics ref, changed files | validation confidence low |
| Build Failure | Build command fails. | error | retry_with_changes | Retry if failure maps to change or environment can be corrected. | 2 | dependency/env failure blocks validation | classify env vs code, adjust patch or escalate dependency | command, exit code, env summary, logs ref | validation confidence low |
| Validation Failure | Static or semantic validation rejects diff. | error | retry_with_changes | Retry only with changed patch/plan/evidence. | 2 | safety violation or scope drift persists | revise patch, narrow scope, return to planning | validation rule, diff ref, acceptance mapping | validation confidence low |
| Lint Failure | Linter reports style or static-quality failure. | warning/error | retry_with_changes | Retry via formatting or patch adjustment if scoped. | 2 | linter unavailable or failures unrelated and broad | inspect lint output, adjust changed files only | command, rules, changed-file hits | validation confidence decreases |
| Formatting Failure | Formatter fails or changed files are not format-compliant. | warning/error | retry_with_changes | Retry formatting only on approved changed files. | 2 | formatter unavailable or modifies unrelated files | run approved formatter scope or revise patch | formatter id, file list, diff refs | patch confidence decreases |
| Test Failure | Tests complete but fail. | error | retry_with_changes | Retry only after diagnosing whether failure is expected, flaky, env, or code. | 2 | repeated same failing test or broad unrelated suite failure | inspect failure, revise root cause/patch/tests | command, test ids, failure snippets, logs ref | validation confidence low |
| Model Output Failure | Agent/model output is incomplete, contradictory, unsafe, or low quality. | warning/error | retry_with_changes | Retry only with stricter prompt, extra context, or alternate agent/model policy. | 2 | repeated invalid reasoning/output | improve prompt constraints, provide artifacts, reselect agent | prompt version/ref, output validation errors | affected agent confidence decreases |
| Malformed Tool Output | Tool output violates response schema or cannot be trusted. | error | retryable or escalate | Retry once if side effects are none or safe. | 1 | repeated malformed output | alternate tool or escalate tool contract issue | schema errors, tool version, output ref | tool evidence confidence invalidated |
| Network Failure | External network dependency fails. | warning/error | retryable | Retry with backoff when idempotent. | 3 | service unavailable beyond policy budget | backoff, alternate endpoint if allowed, cached artifact | endpoint class, status class, duration | stage confidence unchanged or delayed |
| Timeout | Operation exceeds timeout. | warning/error | retryable or retry_with_changes | Retry with narrower scope, adjusted timeout, or alternate tool. | 2 | repeated timeout or unknown side effects | reduce scope, split work, increase timeout by policy | duration, timeout class, partial outputs | confidence decreases for incomplete evidence |
| Memory Failure | Memory lookup, write proposal, or recall is unavailable. | warning/error | retryable or escalate | Retry if memory is required by policy; otherwise continue without memory. | 1 | required memory/audit-linked retention unavailable | retry memory service, proceed with explicit gap, escalate if required | memory operation, object refs, retention class | historical confidence decreases |
| State Corruption | Workflow state is inconsistent, stale, missing, or violates transition rules. | critical | terminal or escalate | No retry until state integrity is restored. | 0 | any unrecoverable state inconsistency | halt, preserve evidence, escalate operator recovery | state snapshot, transition, lock refs, corruption class | overall confidence blocked |
| Unexpected Exception | Unclassified runtime or orchestration exception. | error/critical | retryable once or escalate | One diagnostic retry only when side effects are known safe. | 1 | repeated or side effects unknown | classify exception, inspect side effects, restore checkpoint | diagnostic ref, side effects, current stage | overall confidence decreases sharply |
| Low Confidence | Required confidence threshold is not met. | warning/error | retry_with_changes | Retry by collecting missing evidence or revising strategy. | 2 | no evidence path raises confidence | search/read more context, reanalyze root cause, escalate ambiguity | confidence fields, missing evidence, threshold | explicit confidence remains low |
| Human Intervention Required | Product, permission, safety, or policy decision requires a human. | error/critical | escalate | No autonomous retry. | 0 | immediate | prepare escalation packet | decision needed, options, evidence refs | blocked |
| Unknown Failure | Failure cannot be classified safely. | critical | escalate or diagnostic once | One diagnostic pass only if side effects are understood. | 1 | unknown persists | classify using failure analysis engine, then escalate | raw bounded diagnostic, artifact refs, side effects | overall confidence unknown/blocked |

## Severity Rules

- `critical` failures block autonomous modification.
- `error` failures require recovery or escalation before the workflow can advance.
- `warning` failures may continue only when policy allows and evidence gaps are recorded.
- `info` failures are non-blocking but still auditable when material.

## Audit Rules

Every material failure must record:

- workflow id and stage;
- agent or tool owner;
- failure type, severity, recoverability, and confidence impact;
- input scope or artifact refs;
- known side effects;
- retry eligibility and remaining budget;
- escalation status;
- redaction status.

Secrets, raw private content, oversized logs, and full generated patches must be stored by approved artifact reference.
