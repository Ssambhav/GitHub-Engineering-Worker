"""Reusable tool validation helpers."""

from tools.exceptions import ToolValidationException
from tools.results import ToolResult


def validate_tool_result(result: ToolResult) -> None:
    if result.success and result.errors:
        raise ToolValidationException("successful tool result cannot include errors")
    if not result.metadata.identifier:
        raise ToolValidationException("tool result metadata must include identifier")
