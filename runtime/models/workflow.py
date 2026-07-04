"""Workflow state models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class WorkflowStage(StrEnum):
    """Canonical workflow stages coordinated by the runtime."""

    RECEIVE_REPOSITORY = "Receive Repository"
    RECEIVE_ISSUE = "Receive Issue"
    UNDERSTAND_ISSUE = "Understand Issue"
    COLLECT_CONTEXT = "Collect Context"
    REPOSITORY_SEARCH = "Repository Search"
    READ_RELEVANT_FILES = "Read Relevant Files"
    ANALYZE_ROOT_CAUSE = "Analyze Root Cause"
    CREATE_ENGINEERING_PLAN = "Create Engineering Plan"
    GENERATE_PATCH = "Generate Patch"
    APPLY_CHANGES = "Apply Changes"
    VALIDATE = "Validate"
    RUN_TESTS = "Run Tests"
    DECISION_POINT = "Decision Point"
    RETRY = "Retry"
    ESCALATE = "Escalate"
    REVIEW = "Review"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class WorkflowState(StrEnum):
    """Runtime execution state."""

    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    WAITING = "waiting"
    RETRYING = "retrying"
    ESCALATING = "escalating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class WorkflowTransition:
    """Workflow transition decision."""

    from_stage: WorkflowStage
    to_stage: WorkflowStage
    reason: str

