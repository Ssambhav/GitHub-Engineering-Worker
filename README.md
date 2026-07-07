# GitHub Engineering Worker

GitHub Engineering Worker is an autonomous OpenClaw-based engineering worker for GitHub Issues. It watches configured repositories, detects open issues, prepares a local workspace, reads the GitHub issue, creates a working branch, launches OpenClaw Agent to inspect and modify the repository, inspects the resulting Git working tree, commits and pushes repository changes, opens a pull request, records audit evidence, generates an engineering report, and notifies developers through Discord.

The worker is designed as a small engineering organization: runtime orchestration coordinates bounded subsystems, and each subsystem owns one responsibility. Configuration decides how autonomous it should be.

## Architecture

```text
GitHub Repository
  |
  v
Worker Watcher -> Persistent Issue Queue -> Pipeline Controller
                                      |
                                      v
Repository Workspace -> Engineering Pipeline -> Confidence Engine
                                      |                |
                                      v                v
                              Patch / Tests       Decision Engine
                                      |                |
                                      v                v
                              Git Workflow      Retry / Escalation
                                      |                |
                                      v                v
                              Pull Request      Audit / Report / Discord
```

Core subsystems:

- `worker/`: daemon, watcher, queue, scheduler, CLI, end-to-end controller, Git workflow.
- `engineering/`: repository analysis, prompt building, provider calls, patch validation/application, tests.
- `github/`: GitHub REST client, workspace management, branch, commit, and pull request services.
- `confidence/`: scoring and reporting support that does not block pull request creation.
- `audit/`: structured JSONL audit trail.
- `reports/`: typed engineering report generation.
- `escalation/`: escalation rules for unsafe or low-confidence work.
- `notifications/` and `discord/`: optional notification delivery.
- `runtime/`, `agents/`, `tools/`, `retry/`, `memory/`, `workflows/`: OpenClaw runtime and engineering support systems.

## Features

- Continuous repository watching.
- Sequential issue processing with persistent queue state.
- Duplicate issue prevention and processed issue history.
- Public repository dry-run support without a GitHub token.
- AI provider fallback to the deterministic mock provider when no AI key is configured.
- OpenClaw Agent-first repository engineering.
- Optional test metadata capture when explicitly enabled.
- Retry and escalation when the agent cannot determine a fix or makes no repository changes.
- Feature branch creation, commit, push, and pull request creation.
- Dry-run pull request creation when GitHub credentials are unavailable.
- Structured audit logging.
- Engineering report persistence.
- Optional Discord webhook notifications.

## Installation

Requires Python 3.12 or newer.

```bash
python -m pip install -e .
```

After installation, the `worker` CLI is available through the package script.

```bash
worker --help
```

## Configuration

Start from the provided examples:

- `.env.example`
- `sample-config/config.example.yaml`
- `sample-config/github.example.yaml`
- `sample-config/provider.example.yaml`
- `sample-config/discord.example.yaml`

Minimum environment for a live repository:

```bash
GITHUB_OWNER=your-org
GITHUB_REPOSITORY=your-repo
GITHUB_TOKEN=ghp_...
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
```

If your OpenClaw install is already authenticated with OpenAI/Codex OAuth, the Discord worker can use that directly and does not require a separate Gemini API key or `OPENAI_API_KEY`.

To force the Discord bot away from a previously selected Gemini default, set:

```bash
WORKER_MODEL=openai/gpt-5.4
```

Then restart the bot so the OpenClaw infer path uses the OpenAI/Codex-backed model explicitly instead of inheriting the last selected provider.

For multiple repositories:

```bash
WORKER_REPOSITORIES=owner/repo,owner/another-repo@main
```

## Quick Start

Run one polling/execution cycle:

```bash
worker once
```

Watch continuously:

```bash
worker watch
```

Process one issue directly:

```bash
worker issue --repo owner/repo --issue 123
```

Run a replay without waiting for the watcher:

```bash
worker replay --repo owner/repo --issue 123
```

Inspect status, queue, reports, and logs:

```bash
worker status
worker queue
worker report
worker logs
```

## CLI Commands

- `worker run`: run using configured scheduling mode.
- `worker watch`: continuously poll configured repositories.
- `worker once`: poll and process at most one queued issue.
- `worker issue --repo <owner/repo> --issue <number>`: enqueue and process an issue.
- `worker retry --repo <owner/repo> --issue <number>`: enqueue a retry attempt.
- `worker replay --repo <owner/repo> --issue <number>`: execute the pipeline controller for one issue.
- `worker report [--execution-id <id>]`: list generated report files.
- `worker queue`: print queued issue keys.
- `worker logs`: print worker audit log content.
- `worker status`: print persisted runtime status.
- `worker health`: run configuration, workspace, GitHub, and provider health checks.
- `worker config validate`: validate worker configuration.

## Worker Lifecycle

1. Load runtime and worker configuration.
2. Start runtime services.
3. Poll configured GitHub repositories.
4. Enqueue new open issues.
5. Skip closed, processed, duplicate, or in-progress issues.
6. Clone or refresh the repository workspace.
7. Create a feature branch.
8. Launch OpenClaw Agent.
9. Let the agent inspect and modify the repository.
10. Inspect the Git working tree.
11. If source files changed, commit, push, and create a pull request.
12. If the agent cannot determine a fix or makes no repository changes, escalate with a clear reason.
14. Persist audit logs and engineering reports.
15. Send optional Discord notification.
16. Sleep until the next schedule.

## Supported AI Providers

- OpenAI through `OPENAI_API_KEY`.
- OpenRouter through `OPENROUTER_API_KEY`.
- Mock provider for offline smoke tests and dry runs.

Provider selection is controlled by `WORKER_PROVIDER`, `WORKER_MODEL`, and engineering configuration.

## Supported Git Providers

The current implementation targets GitHub through the existing GitHub integration. The repository and tool boundaries are intentionally provider-aware, but live support is GitHub-only in this milestone.

## Repository Requirements

Target repositories should:

- Be cloneable by the configured GitHub token or publicly cloneable for dry runs.
- Have a valid default branch.
- Allow feature branch pushes for live PR creation.
- Permit feature branch pushes for autonomous pull request creation.
- Be safe for automated patch generation and review.

The worker never commits directly to the default branch.

## Discord Integration

Discord notifications are optional. The worker continues operating if Discord is unavailable.

Enable Discord:

```bash
DISCORD_ENABLED=true
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
```

Notification types include worker started, issue detected, issue solved, pull request created, retry started, retry failed, escalation, worker error, and health warning.

The interactive Discord AI worker uses `OpenClawProvider`, which calls `openclaw infer model run` and follows the active OpenClaw auth/model selection. In this workspace, that means the selected provider can be your Codex/OpenAI OAuth login instead of a Gemini API key.

## Engineering Pipeline

The engineering pipeline performs:

- repository search
- context building
- prompt construction
- provider call
- patch generation
- patch validation
- patch application
- repository validation
- test detection
- optional test execution

When no AI provider key exists, the mock provider returns a deterministic patch for smoke testing.

## Environment Variables

Common variables:

- `GITHUB_OWNER`
- `GITHUB_REPOSITORY`
- `WORKER_REPOSITORIES`
- `GITHUB_TOKEN`
- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`
- `WORKER_PROVIDER`
- `WORKER_MODEL`
- `DISCORD_ENABLED`
- `DISCORD_WEBHOOK`
- `WORKER_POLL_INTERVAL_MINUTES`
- `WORKER_AUTO_CREATE_PR`
- `WORKER_AUTO_PUSH`
- `WORKER_AUTO_COMMIT`
- `WORKER_AUTO_CLEANUP`
- `WORKER_CONTINUE_ON_FAILURE`
- `WORKER_CONFIDENCE_THRESHOLD`
- `WORKER_RUN_TESTS`

## Example Workflow

```text
Issue #42 opened
Worker detects owner/repo#42
Repository cloned to workspace
Feature branch gew/issue-42-fix-login-error created
Engineering pipeline generates patch
Patch validates and tests pass
Confidence: 86.4 high
Worker commits and pushes branch
Pull request opened
Audit and report persisted
Discord success notification sent
```

See `examples/` and `demo/` for sample output and runnable demonstration material.

## Example Output

```text
Pull Request Created
Issue: owner/repo#42
Branch: gew/issue-42-fix-login-error
Confidence: 86.4
Decision: proceed
Report: reports/worker/worker_owner_repo_42.json
```

## Failure Handling

If a stage fails, the controller records audit evidence, generates a report, evaluates recoverability, and either retries or escalates. A single issue failure does not stop the worker from watching or processing later issues when `WORKER_CONTINUE_ON_FAILURE=true`.

## Confidence

The confidence engine scores issue understanding, repository understanding, repository search, context quality, prompt quality, AI response, patch quality, validation, tests, retry count, and failure history.

Default decision bands:

- `90-100`: very high, auto PR.
- `75-89`: high, proceed.
- `60-74`: medium, retry allowed.
- `40-59`: low, gather more context.
- `<40`: critical, escalate.

## Retry

Retries are bounded by configuration. The worker retries recoverable issue failures and marks issues escalated after the retry budget is exhausted.

## Escalation

Escalation occurs when confidence is too low, retry limits are exceeded, unsafe patch evidence appears, repeated failures occur, repository corruption is detected, provider availability blocks execution, or an unknown failure remains.

## Audit

Audit entries are JSONL records containing execution ID, issue, repository, stage, action, result, confidence, retry count, duration, and metadata. They are queryable through the audit logger and visible through `worker logs`.

## Roadmap

- Additional git providers.
- Richer report rendering formats.
- Hosted dashboard for worker status.
- More granular confidence signals from each engineering artifact.
- CI-native deployment templates.

## Limitations

- Live PR creation requires a GitHub token with clone, push, and pull request permissions.
- Real patch quality depends on the configured AI provider and repository context quality.
- Discord delivery requires a valid webhook.
- The mock provider is intended for smoke tests, not production fixes.

## Future Improvements

Future improvements are separate from required functionality: Docker packaging, GitHub Actions workflows, hosted demo assets, video demos, dashboards, and additional provider integrations.
