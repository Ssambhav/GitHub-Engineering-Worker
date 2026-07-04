# Tools Directory

This directory is reserved for future tool adapters and category-specific documentation for GitHub Engineering Worker.

The authoritative Tool Framework is [../TOOLS.md](../TOOLS.md). Tool specifications live under [../docs/specifications](../docs/specifications/README.md).

## Current Boundary

This repository currently defines tool architecture and contracts only. Do not add tool implementation code, external integrations, workflow logic, or business logic unless that work is explicitly scoped separately.

## Expected Future Structure

Tool directories should align with registered categories:

- `github/`: GitHub API tools.
- `git/`: Git worktree and repository metadata tools.
- `ci/`: validation and test execution integrations.
- `code-analysis/`: static analysis, lint, format, and syntax tools.
- `security/`: security scanning and policy validation tools.
- `notifications/`: authorized human notification tools.

Each future tool must have a contract, registry entry, permission declaration, validation rules, failure mapping, and audit requirements before implementation.
