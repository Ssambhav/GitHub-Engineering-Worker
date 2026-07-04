"""Agent registration and discovery utilities."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Type

from runtime.exceptions import RegistryException
from runtime.registry import RuntimeRegistry

from agents.base import EngineeringAgent
from agents.configuration import AgentConfiguration
from agents.contracts import RuntimeServices


def discover_agent_types() -> tuple[Type[EngineeringAgent], ...]:
    from agents.implementations import (
        IssueUnderstandingAgent,
        PlanningAgent,
        RepositoryContextAgent,
        ReviewGenerationAgent,
        ValidationAgent,
    )

    return (
        IssueUnderstandingAgent,
        RepositoryContextAgent,
        PlanningAgent,
        ValidationAgent,
        ReviewGenerationAgent,
    )


CORE_AGENT_TYPES = discover_agent_types


def register_agent(
    registry: RuntimeRegistry,
    agent_type: Type[EngineeringAgent],
    *,
    configuration: AgentConfiguration | None = None,
    services: RuntimeServices | None = None,
) -> EngineeringAgent:
    """Instantiate and register one agent implementation."""

    agent = agent_type(configuration=configuration, services=services)
    metadata = agent.runtime_metadata()
    if registry.agents.contains(metadata.identifier):
        raise RegistryException(f"agent already registered: {metadata.identifier}")
    _validate_version(metadata.version)
    registry.agents.register(metadata, agent)
    return agent


def register_core_agents(
    registry: RuntimeRegistry,
    *,
    configuration: AgentConfiguration | None = None,
    services: RuntimeServices | None = None,
    agent_types: Iterable[Type[EngineeringAgent]] | None = None,
) -> tuple[EngineeringAgent, ...]:
    """Register the built-in first set of engineering agents."""

    registered: list[EngineeringAgent] = []
    for agent_type in agent_types or discover_agent_types():
        registered.append(
            register_agent(
                registry,
                agent_type,
                configuration=configuration,
                services=services,
            )
        )
    return tuple(registered)


def _validate_version(version: str) -> None:
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise RegistryException(f"agent version must use semantic versioning: {version}")
