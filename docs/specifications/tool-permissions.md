# Tool Permission Specification

Tool permissions define what an agent or workflow is allowed to request through the Tool Framework. Permissions are validated before execution and must be scoped as narrowly as possible.

The canonical Tool Framework is [TOOLS.md](../../TOOLS.md).

## Principles

- Deny by default.
- Grant only the permissions needed for the current phase.
- Scope permissions by repository, path, command, network domain, memory namespace, state object, or audit operation.
- Validate both permission type and side-effect class.
- Treat permission denial as a structured tool failure.
- Audit denied requests when policy requires.

## Permission Categories

| Permission | Allows | Typical agents |
| --- | --- | --- |
| Read Repository | Inspect repository tree, files, metadata, diffs. | Repository Context, Search, File Reader, Root Cause Analysis. |
| Modify Repository | Write files, apply patches, format modified files. | Code Modification. |
| Execute Commands | Run approved local commands, tests, linters, formatters. | Test Execution, Validation. |
| Git Operations | Inspect or mutate Git state depending on scope. | Validation, Code Modification, Review Generation. |
| GitHub Read | Read issues, comments, PRs, checks, repo metadata. | Issue Understanding, Review Generation. |
| GitHub Write | Comment, label, update issue/PR state, open PRs. | Escalation or Review agents when authorized. |
| Network Access | Contact external services. | GitHub tools, dependency tools when authorized. |
| Read Memory | Query or read durable memory. | Orchestrator, Memory Management, Planning, Retry & Recovery. |
| Write Memory | Propose or persist memory updates. | Memory Management. |
| Audit Logging | Append or read audit records. | All agents through Audit Logging. |
| State Read | Read workflow state snapshots. | Orchestrator, State Management, selected specialists. |
| State Write | Update lifecycle state, locks, checkpoints. | State Management. |
| Administrative Operations | Register, deprecate, retire tools, update policies. | Operators or administrative agents only. |
| Secret Access | Access credentials through approved secret mechanisms. | Narrow tool implementations only, never general agents. |

## Scope Model

Permissions should include scope:

```yaml
permission: Modify Repository
subject: Code Modification Agent
scope:
  repository: owner/repo
  paths:
    - src/approved-file.ts
  operation:
    - apply_patch
  phase:
    - execute
  expires_at: timestamp or workflow phase end
```

## Validation Before Execution

The framework validates:

- Subject identity.
- Tool permission requirements.
- Granted permissions.
- Scope compatibility.
- Workflow phase.
- Side-effect allowance.
- Lock ownership when required.
- Audit availability.
- Secret policy.
- Timeout and resource policy.

## Permission Denial

Denied requests return:

```yaml
status: denied
failure:
  category: Permission Denied
  severity: error | critical
  recoverability: not_retryable
  message: bounded reason
retry:
  recommended: false
  safe_to_retry: false
  requires_changed_input: true
```

Denials should not expose secret policy internals. They should provide enough information for the orchestrator to escalate or choose another path.

## Side-Effect Classes

Permissions must also validate side effects:

- read: observes data without mutation.
- write: modifies repository, files, memory, state, GitHub, or audit store.
- execute: runs local processes or commands.
- network: contacts remote systems.
- administrative: changes registry, policy, or platform configuration.

Tools declaring side effects not allowed in the current phase must be denied.

## Escalation

Escalate when a required permission is absent and the workflow cannot proceed safely. Escalation packets should include the permission needed, scope, reason, and risk of granting or denying it.
