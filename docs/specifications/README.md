# Specifications

Formal project specifications belong here. These documents define contracts before implementation begins.

## Current Specifications

- [Agent Contract](agent-contract.md): required contract shape for every production agent.
- [Agent Communication](agent-communication.md): structured message, event, shared context, and synchronization model.
- [Issue Lifecycle](issue-lifecycle.md): lifecycle expectations for GitHub Issue ownership.
- [Tool Contract](tool-contract.md): required contract shape for every production tool.
- [Tool Registry](tool-registry.md): discovery, registration, ownership, aliases, versioning, and deprecation.
- [Tool Invocation](tool-invocation.md): request/response model, streaming, cancellation, timeouts, and validation.
- [Tool Permissions](tool-permissions.md): permission categories, scope model, validation, and denial behavior.
- [Tool Failures](tool-failures.md): shared failure taxonomy, retry behavior, audit requirements, and escalation expectations.
- [Workflow Contract](workflow-contract.md): workflow, stage, decision, event, checkpoint, and branch contracts.
- [State Machine Contract](state-machine-contract.md): execution state, transition, snapshot, validation, and event contracts.
- [Memory Object Contract](memory-object-contract.md): required contract shape for structured memory object families.
- [Memory Access Contract](memory-access-contract.md): read, write, append, merge, query, snapshot, restore, lock, and unlock contracts.
- [Memory Checkpoint Contract](memory-checkpoint-contract.md): memory refs, version pins, and restoration requirements for recoverability.
- [Retry & Recovery Specification](retry-recovery.md): retry artifacts, policies, decisions, escalation, and safety invariants.
- [Retry Contracts](../../retry/contracts/README.md): failure analysis, recovery plan, retry strategy, and retry outcome contracts.

The canonical agent architecture is [AGENTS.md](../../AGENTS.md).
The canonical tool architecture is [TOOLS.md](../../TOOLS.md).
The canonical workflow architecture is [WORKFLOW.md](../../WORKFLOW.md).
The canonical state machine architecture is [STATES.md](../../STATES.md).
The canonical memory architecture is [memory/MEMORY.md](../../memory/MEMORY.md).
The canonical retry architecture is [retry/README.md](../../retry/README.md).
