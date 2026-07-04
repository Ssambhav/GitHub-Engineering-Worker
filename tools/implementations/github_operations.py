"""GitHub repository preparation tools."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping

from github.configuration import GitHubIntegrationConfig
from github.services import GitHubPreparationService
from tools.base import EngineeringTool
from tools.context import ToolContext, ToolRequest
from tools.metadata import ToolCapabilities, ToolMetadata
from tools.results import ToolArtifact, ToolResult


class GitHubRepositoryTool(EngineeringTool):
    metadata = ToolMetadata(
        identifier="github.repository",
        name="GitHub Repository Tool",
        version="1.0.0",
        description="Read GitHub repository metadata.",
        capabilities=ToolCapabilities(("github.repository.read", "github.metadata")),
    )

    @classmethod
    def required_inputs(cls) -> tuple[str, ...]:
        return ("owner", "repo")

    def execute(self, request: ToolRequest, context: ToolContext, prepared: Mapping[str, Any]) -> ToolResult:
        service = _service(context)
        repository = service.client.get_repository(str(request.inputs["owner"]), str(request.inputs["repo"]))
        return ToolResult.ok(metadata=self.metadata, structured_output=_to_json(repository))


class GitHubIssueTool(EngineeringTool):
    metadata = ToolMetadata(
        identifier="github.issue",
        name="GitHub Issue Tool",
        version="1.0.0",
        description="Read GitHub issue data, labels, comments, and open issue lists.",
        capabilities=ToolCapabilities(("github.issue.read", "github.issue.list", "github.labels.read")),
    )

    @classmethod
    def required_inputs(cls) -> tuple[str, ...]:
        return ("owner", "repo")

    def execute(self, request: ToolRequest, context: ToolContext, prepared: Mapping[str, Any]) -> ToolResult:
        service = _service(context)
        owner = str(request.inputs["owner"])
        repo = str(request.inputs["repo"])
        if "issue_number" in request.inputs:
            number = int(request.inputs["issue_number"])
            issue = service.issues.read_issue(owner, repo, number)
            comments = service.issues.read_comments(owner, repo, number) if request.inputs.get("include_comments") else ()
            output = {"issue": _to_json(issue), "comments": [_to_json(comment) for comment in comments]}
        else:
            issues = service.issues.list_open_issues(owner, repo, limit=int(request.inputs.get("limit", 30)))
            output = {"issues": [_to_json(issue) for issue in issues]}
        if request.inputs.get("include_labels"):
            output["labels"] = list(service.issues.read_labels(owner, repo))
        return ToolResult.ok(metadata=self.metadata, structured_output=output)


class GitHubWorkspaceTool(EngineeringTool):
    metadata = ToolMetadata(
        identifier="github.workspace",
        name="GitHub Workspace Tool",
        version="1.0.0",
        description="Clone, reuse, refresh, inspect, and clean local GitHub workspaces.",
        capabilities=ToolCapabilities(("github.clone", "repository.workspace", "git.status")),
        side_effects=("read", "write", "execute", "network"),
        idempotency="conditionally_idempotent",
    )

    @classmethod
    def required_inputs(cls) -> tuple[str, ...]:
        return ("owner", "repo")

    def execute(self, request: ToolRequest, context: ToolContext, prepared: Mapping[str, Any]) -> ToolResult:
        service = _service(context)
        owner = str(request.inputs["owner"])
        repo = str(request.inputs["repo"])
        repository, path = service.prepare_repository(owner, repo, temporary=bool(request.inputs.get("temporary", False)))
        state = service.status(path, repository.full_name)
        artifact = ToolArtifact("github-workspace", "repository_workspace", str(path), {"repository": repository.full_name})
        return ToolResult.ok(
            metadata=self.metadata,
            structured_output={"repository": _to_json(repository), "workspace": _to_json(state)},
            artifacts=(artifact,),
        )


class GitHubBranchTool(EngineeringTool):
    metadata = ToolMetadata(
        identifier="github.branch",
        name="GitHub Branch Tool",
        version="1.0.0",
        description="Create, checkout, delete, and inspect local repository branches.",
        capabilities=ToolCapabilities(("git.branch", "github.branch")),
        side_effects=("write", "execute"),
        idempotency="conditionally_idempotent",
    )

    @classmethod
    def required_inputs(cls) -> tuple[str, ...]:
        return ("path", "branch")

    def execute(self, request: ToolRequest, context: ToolContext, prepared: Mapping[str, Any]) -> ToolResult:
        service = _service(context)
        path = Path(str(request.inputs["path"]))
        action = str(request.inputs.get("action", "create"))
        branch = str(request.inputs["branch"])
        if action == "create":
            service.repository_operations.create_branch(path, branch, base=_optional(request.inputs.get("base")), reset_existing=True)
        elif action == "checkout":
            service.repository_operations.checkout_branch(path, branch)
        elif action == "delete":
            service.repository_operations.delete_branch(path, branch, force=bool(request.inputs.get("force", False)))
        else:
            raise ValueError(f"unsupported branch action: {action}")
        return ToolResult.ok(metadata=self.metadata, structured_output={"branch": service.repository_operations.current_branch(path)})


class GitHubCommitTool(EngineeringTool):
    metadata = ToolMetadata(
        identifier="github.commit",
        name="GitHub Commit Tool",
        version="1.0.0",
        description="Stage files, create commits, push branches, and rollback commits.",
        capabilities=ToolCapabilities(("git.commit", "git.push", "git.rollback")),
        side_effects=("write", "execute", "network"),
        idempotency="non_idempotent",
    )

    @classmethod
    def required_inputs(cls) -> tuple[str, ...]:
        return ("path", "action")

    def execute(self, request: ToolRequest, context: ToolContext, prepared: Mapping[str, Any]) -> ToolResult:
        service = _service(context)
        path = Path(str(request.inputs["path"]))
        action = str(request.inputs["action"])
        if action == "commit":
            sha = service.repository_operations.commit(
                path,
                str(request.inputs["message"]),
                allow_empty=bool(request.inputs.get("allow_empty", False)),
            )
            output = {"commit": sha}
        elif action == "stage":
            files = tuple(str(item) for item in request.inputs.get("files", ())) or None
            service.repository_operations.stage_files(path, files)
            output = {"staged": True}
        elif action == "push":
            service.repository_operations.push_branch(
                path,
                str(request.inputs["branch"]),
                remote=str(request.inputs.get("remote", "origin")),
                dry_run=bool(request.inputs.get("dry_run", context.execution.metadata.dry_run)),
            )
            output = {"pushed": True, "dry_run": bool(request.inputs.get("dry_run", context.execution.metadata.dry_run))}
        elif action == "rollback":
            service.repository_operations.rollback_last_commit(path, keep_changes=bool(request.inputs.get("keep_changes", True)))
            output = {"rolled_back": True}
        else:
            raise ValueError(f"unsupported commit action: {action}")
        return ToolResult.ok(metadata=self.metadata, structured_output=output)


class GitHubPullRequestTool(EngineeringTool):
    metadata = ToolMetadata(
        identifier="github.pull_request",
        name="GitHub Pull Request Tool",
        version="1.0.0",
        description="Create, update, validate, or dry-run GitHub pull requests.",
        capabilities=ToolCapabilities(("github.pull_request.create", "github.pull_request.update")),
        side_effects=("write", "network"),
        idempotency="non_idempotent",
    )

    @classmethod
    def required_inputs(cls) -> tuple[str, ...]:
        return ("owner", "repo", "issue_number", "issue_title", "summary", "head", "base")

    def execute(self, request: ToolRequest, context: ToolContext, prepared: Mapping[str, Any]) -> ToolResult:
        service = _service(context)
        pr = service.pull_requests.create_pr(
            str(request.inputs["owner"]),
            str(request.inputs["repo"]),
            issue_number=int(request.inputs["issue_number"]),
            issue_title=str(request.inputs["issue_title"]),
            summary=str(request.inputs["summary"]),
            head=str(request.inputs["head"]),
            base=str(request.inputs["base"]),
            dry_run=bool(request.inputs.get("dry_run", context.execution.metadata.dry_run)),
            draft=bool(request.inputs.get("draft", False)),
        )
        return ToolResult.ok(metadata=self.metadata, structured_output=_to_json(pr))


def _service(context: ToolContext) -> GitHubPreparationService:
    runtime_config = getattr(context.runtime_services, "configuration", None)
    github_config = None if runtime_config is None else getattr(runtime_config, "github", None)
    config = GitHubIntegrationConfig.from_environment(
        token_env=getattr(github_config, "token_env", "GITHUB_TOKEN"),
        workspace_path=getattr(github_config, "workspace_path", ".workspaces"),
        branch_naming_template=getattr(github_config, "branch_naming_template", "gew/issue-{issue_number}-{slug}"),
        commit_message_template=getattr(github_config, "commit_message_template", "Fix issue #{issue_number}: {title}"),
        pr_body_template=getattr(github_config, "pr_template", "{summary}\n\nCloses #{issue_number}"),
        cleanup_policy=getattr(github_config, "cleanup_policy", "keep"),
        rate_limit_threshold=getattr(github_config, "rate_limit_threshold", 25),
    )
    return GitHubPreparationService.create(config)


def _to_json(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _to_json(item) for key, item in asdict(value).items()}
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_to_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_json(item) for key, item in value.items()}
    return value


def _optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None
