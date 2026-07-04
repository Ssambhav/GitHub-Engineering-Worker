"""Typed configuration for engineering agents."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import Any, Mapping

from runtime.models.common import immutable_mapping

from agents.exceptions import AgentConfigurationException


@dataclass(frozen=True, slots=True)
class AgentConfiguration:
    """Configuration shared by all engineering agents."""

    enabled: bool = True
    timeout_seconds: int = 300
    confidence_threshold: float = 0.5
    publish_lifecycle_events: bool = True
    metadata: Mapping[str, Any] = field(default_factory=immutable_mapping)

    def validate(self) -> None:
        if self.timeout_seconds <= 0:
            raise AgentConfigurationException("timeout_seconds must be positive")
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise AgentConfigurationException("confidence_threshold must be between 0.0 and 1.0")

    def with_environment_overrides(self, prefix: str) -> "AgentConfiguration":
        """Return a copy with supported environment overrides applied."""

        timeout = os.getenv(f"{prefix}_TIMEOUT_SECONDS")
        threshold = os.getenv(f"{prefix}_CONFIDENCE_THRESHOLD")
        enabled = os.getenv(f"{prefix}_ENABLED")
        updated = self
        if timeout is not None:
            updated = replace(updated, timeout_seconds=int(timeout))
        if threshold is not None:
            updated = replace(updated, confidence_threshold=float(threshold))
        if enabled is not None:
            updated = replace(updated, enabled=enabled.strip().lower() in {"1", "true", "yes", "on"})
        updated.validate()
        return updated
