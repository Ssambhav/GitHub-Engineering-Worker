# Recovery Strategies

Recovery strategies describe how a failed attempt can become a better attempt. They are selected by policy and failure analysis; they are not algorithms.

## Strategy Families

- `refresh_context`: update repository, issue, state, or memory evidence.
- `narrow_scope`: reduce search, test, patch, or tool input scope.
- `alternate_tool`: choose a different registered tool capability.
- `alternate_agent`: route to a different specialist agent or stricter output contract.
- `prompt_refinement`: add constraints, examples, or missing evidence to a model request.
- `root_cause_revision`: return to analysis with disproving evidence.
- `plan_revision`: adjust implementation or validation plan.
- `patch_revision`: regenerate or repair patch proposal.
- `checkpoint_restore`: return repository/workflow state to a known safe checkpoint.
- `validation_expansion`: add targeted checks needed to prove recovery.
- `escalation`: stop autonomous recovery and request human/operator decision.

## Strategy Contract

```yaml
strategy_id: retry.strategy.patch_revision
strategy_version: 1.0.0
description: Regenerate a patch after validation, application, build, or test failure.
applies_to_failure_types:
  - Patch Application Failure
  - Validation Failure
  - Test Failure
entry_requirements:
  - failure analysis exists
  - changed strategy is identified
  - patch scope remains approved
actions_to_request:
  - collect missing file context when needed
  - update patch proposal
  - revalidate diff
forbidden_actions:
  - modify unapproved files
  - reuse identical patch
  - skip validation
completion_evidence:
  - new patch proposal ref
  - anti-duplicate comparison ref
  - validation report ref
confidence_effect:
  on_success: increase patch and validation confidence
  on_failure: decrease patch confidence and consider escalation
```

## Selection Rules

- Prefer the earliest strategy that addresses the invalid assumption.
- Prefer evidence-gathering over patch changes when root cause confidence is low.
- Prefer patch revision over root-cause revision only when the cause remains supported.
- Prefer escalation when the failed assumption is a product, permission, state, or safety issue.
