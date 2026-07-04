# Tool Registry Specification

The Tool Registry is the authoritative catalog of tools available to GitHub Engineering Worker. It enables capability-based discovery, permission-aware selection, version control, ownership, deprecation, and safe extensibility.

The canonical Tool Framework is [TOOLS.md](../../TOOLS.md).

## Responsibilities

The registry must:

- Store canonical tool metadata and contract references.
- Support lookup by tool id, alias, category, capability, permission, owner, and version.
- Expose only active and policy-compatible tools for new invocations.
- Preserve historical metadata for audit reconstruction.
- Track deprecation, retirement, and replacement tools.
- Validate that registered tools declare required contract fields.
- Allow new tools to satisfy existing capabilities without modifying agents.

## Registry Entry

```yaml
tool_id: stable canonical identifier
name: human-readable name
version:
  contract: semantic contract version
  implementation: implementation release version
category: logical tool category
capabilities:
  - capability identifiers
aliases:
  - optional alternate names
owner: owning team, module, or maintainer
description: concise purpose
contract_ref: contract document or registry object
permissions_required:
  - permission identifiers
side_effects:
  - none | read | write | execute | network | state | memory | audit
idempotency: idempotent | conditionally_idempotent | non_idempotent
expected_execution_time: short | medium | long | variable
timeout_policy: timeout class
retry_policy: retry class
output_schema: schema identifier
audit_level: none | metadata | full | security_sensitive
status: active | experimental | deprecated | retired
replacement: optional successor tool id
compatibility:
  runtimes:
    - supported runtime
  platforms:
    - supported platform
  contract_versions:
    - supported contract range
created_at: timestamp
updated_at: timestamp
```

## Discovery Modes

### Capability Lookup

Agents and orchestration should prefer capability lookup over hardcoded tool ids.

Example intent: find an active tool that can read GitHub Issue comments under GitHub Read permission.

### Category Lookup

Used when an agent needs a family of tools, such as Search Tools or Testing Tools.

### Permission-Aware Lookup

Filters tools based on the requester's permission context and current workflow phase.

### Version Lookup

Finds tools compatible with a required contract or capability version.

### Alias Lookup

Resolves friendly or legacy names to canonical tool ids. Alias resolution must be auditable when ambiguity exists.

## Registration

Registration requires:

- Complete tool contract.
- Registry metadata.
- Owner assignment.
- Permission declaration.
- Side effect declaration.
- Validation schema.
- Failure taxonomy mapping.
- Audit requirement declaration.
- Compatibility declaration.

Experimental tools may be registered but must not be selected for production workflows unless policy explicitly allows them.

## Versioning

The registry tracks three version concepts:

- Contract version: request/response and behavioral guarantees.
- Implementation version: internal tool implementation version.
- Capability version: semantic domain capability version.

Backward-compatible contract changes may add optional fields. Breaking changes require a new major version or new tool id.

## Ownership

Each tool must have an owner responsible for:

- Contract accuracy.
- Safety constraints.
- Permission declarations.
- Failure mapping.
- Validation rules.
- Deprecation and retirement.

## Deprecation

Deprecated tools remain available only when policy allows. Registry entries should include:

- Deprecation reason.
- Replacement tool id.
- Migration notes.
- Removal target.
- Known risks.

Retired tools must not be selected for new invocations, but metadata must remain available for historical audit records.

## Extensibility

New tools can be added without modifying existing agents when they:

- Register an existing capability.
- Honor the existing contract version.
- Declare compatible permissions and output schemas.
- Are selected through capability lookup by the orchestrator or tool access layer.

Agents should request capabilities and constraints, not implementation-specific tool names.
