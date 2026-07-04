# Tool Framework Overview

GitHub Engineering Worker uses tools as controlled execution boundaries. Agents do not directly read files, call GitHub, run tests, write code, update memory, or mutate state. They request capabilities from registered tools under explicit contracts and permissions.

The canonical framework is [TOOLS.md](../TOOLS.md).

## Framework Responsibilities

The Tool Framework provides:

- Tool discovery through a registry.
- Contract-based invocation.
- Permission validation.
- Input and output validation.
- Timeout and cancellation handling.
- Synchronous and asynchronous execution models.
- Retry-aware failure reports.
- Audit logging of material invocations.
- Versioning, ownership, deprecation, and retirement.

## Tool Categories

Required logical categories:

- Repository Tools.
- GitHub Tools.
- File System Tools.
- Search Tools.
- Code Modification Tools.
- Validation Tools.
- Testing Tools.
- Git Tools.
- Memory Tools.
- Audit Tools.
- State Tools.
- Utility Tools.
- System Tools.

Categories are extensible. Adding a category should not require changing the orchestration architecture when capability lookup and contracts remain stable.

## Key Specifications

- [Tool Contract](specifications/tool-contract.md): required fields and reusable contract template.
- [Tool Registry](specifications/tool-registry.md): discovery, registration, ownership, aliases, versioning, and deprecation.
- [Tool Invocation](specifications/tool-invocation.md): request/response model, streaming, cancellation, timeouts, and result validation.
- [Tool Permissions](specifications/tool-permissions.md): permission categories, scope, validation, and denial behavior.
- [Tool Failures](specifications/tool-failures.md): shared failure taxonomy and retry/escalation expectations.

## Agent Interaction Model

Agents request capabilities; the registry resolves compatible tools. The framework validates the request before execution and validates the response before returning it to the agent.

Agents should not:

- Bypass tool contracts.
- Assume implementation details.
- Retry failures without using failure recoverability guidance.
- Treat unvalidated output as evidence.
- Perform side effects outside tools.

## Extension Model

New tools are added by:

1. Defining a contract.
2. Declaring permissions and side effects.
3. Registering metadata and capability identifiers.
4. Providing validation and failure taxonomy mapping.
5. Marking lifecycle status as experimental, active, deprecated, or retired.

Existing agents should continue to request capabilities rather than being rewritten for a specific new tool.
