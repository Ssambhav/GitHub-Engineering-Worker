"""Runtime composition root."""

from __future__ import annotations

from dataclasses import dataclass, field

from runtime.configuration import RuntimeConfiguration, RuntimeConfigurationProvider
from runtime.context import ExecutionContext, ExecutionContextBuilder
from runtime.dispatcher import RegisteredAgentDispatcher
from runtime.events import InMemoryEventBus
from runtime.lifecycle import LifecycleManager, ShutdownManager
from runtime.models.common import IssueRef, RepositoryRef
from runtime.orchestrator import EngineeringOrchestrator, ExecutionSummary
from runtime.registry import RuntimeRegistry
from runtime.scheduler import InlineScheduler
from runtime.sessions import SessionManager


@dataclass(slots=True)
class ExecutionRuntime:
    """Composition root for runtime core services."""

    configuration_provider: RuntimeConfigurationProvider = field(default_factory=RuntimeConfigurationProvider)
    configuration: RuntimeConfiguration | None = None
    registry: RuntimeRegistry = field(default_factory=RuntimeRegistry)
    event_bus: InMemoryEventBus = field(default_factory=InMemoryEventBus)
    session_manager: SessionManager = field(default_factory=SessionManager)
    scheduler: InlineScheduler = field(default_factory=InlineScheduler)
    shutdown_manager: ShutdownManager = field(default_factory=ShutdownManager)
    dispatcher: RegisteredAgentDispatcher = field(init=False)
    lifecycle: LifecycleManager = field(init=False)
    context_builder: ExecutionContextBuilder = field(init=False)
    tool_registry: object = field(init=False)
    tool_executor: object | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.dispatcher = RegisteredAgentDispatcher(self.registry)
        self.lifecycle = LifecycleManager(self.event_bus, self.shutdown_manager)
        self.context_builder = ExecutionContextBuilder()
        from tools.registry import ToolRegistry

        self.tool_registry = ToolRegistry(self.registry)

    def start(self) -> None:
        """Initialize the runtime."""

        if self.configuration is None:
            self.configuration = self.configuration_provider.load()
        self._register_core_agents()
        self._register_core_tools()
        self.lifecycle.initialize()

    def shutdown(self, reason: str | None = None) -> None:
        """Request runtime shutdown and cleanup."""

        self.lifecycle.shutdown(reason)

    def create_context(self, *, issue: IssueRef, repository: RepositoryRef) -> ExecutionContext:
        """Create an initial execution context from runtime configuration."""

        if self.configuration is None:
            self.start()
        assert self.configuration is not None
        return self.context_builder.create(
            issue=issue,
            repository=repository,
            environment=self.configuration.project.environment,
            dry_run=self.configuration.execution.dry_run,
            labels={"project": self.configuration.project.name},
        )

    def run_workflow(self, *, issue: IssueRef, repository: RepositoryRef) -> ExecutionSummary:
        """Create an execution context and run the engineering orchestrator."""

        if self.configuration is None:
            self.start()
        context = self.create_context(issue=issue, repository=repository)
        orchestrator = EngineeringOrchestrator(
            registry=self.registry,
            dispatcher=self.dispatcher,
            event_bus=self.event_bus,
            session_manager=self.session_manager,
            scheduler=self.scheduler,
        )
        return orchestrator.run(context)

    def _register_core_agents(self) -> None:
        """Register built-in agents once."""

        from agents.contracts import RuntimeServices
        from agents.registry import discover_agent_types, register_core_agents

        agent_types = tuple(
            agent_type
            for agent_type in discover_agent_types()
            if not self.registry.agents.contains(agent_type.metadata.identifier)
        )
        if not agent_types:
            return
        register_core_agents(
            self.registry,
            services=RuntimeServices(registry=self.registry, event_bus=self.event_bus),
            agent_types=agent_types,
        )

    def _register_core_tools(self) -> None:
        """Register built-in tools and create the runtime tool executor."""

        from agents.contracts import RuntimeServices
        from tools.configuration import ToolConfiguration
        from tools.executor import ToolExecutor
        from tools.registry import register_core_tools

        register_core_tools(self.registry)
        assert self.configuration is not None
        services = RuntimeServices(registry=self.registry, event_bus=self.event_bus)
        tool_configuration = ToolConfiguration.from_environment(self.configuration.openclaw.workspace)
        self.tool_executor = ToolExecutor(self.tool_registry, services, tool_configuration)
