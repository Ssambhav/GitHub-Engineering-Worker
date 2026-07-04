"""Runtime core for GitHub Engineering Worker.

The runtime package coordinates workflows, agents, tools, events, sessions,
state-facing context updates, and lifecycle concerns. It intentionally contains
no GitHub API integration, repository analysis, patch generation, or issue
solving logic.
"""

from runtime.configuration import RuntimeConfiguration, RuntimeConfigurationProvider
from runtime.context import ExecutionContext, ExecutionContextBuilder
from runtime.execution import ExecutionRuntime
from runtime.orchestrator import EngineeringOrchestrator

__all__ = [
    "EngineeringOrchestrator",
    "ExecutionContext",
    "ExecutionContextBuilder",
    "ExecutionRuntime",
    "RuntimeConfiguration",
    "RuntimeConfigurationProvider",
]

