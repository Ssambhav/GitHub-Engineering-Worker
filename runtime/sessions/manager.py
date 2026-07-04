"""Execution session management."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from threading import RLock
from uuid import uuid4

from runtime.context import ExecutionContext
from runtime.exceptions import RuntimeException
from runtime.models.common import utc_now


@dataclass(frozen=True, slots=True)
class RuntimeSession:
    """A runtime session owns one execution context lifecycle."""

    session_id: str
    context: ExecutionContext
    created_at: object = field(default_factory=utc_now)
    closed_at: object | None = None

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None

    def close(self) -> "RuntimeSession":
        return replace(self, closed_at=utc_now())


class SessionManager:
    """Creates and tracks runtime sessions."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._sessions: dict[str, RuntimeSession] = {}

    def create_session(self, context: ExecutionContext) -> RuntimeSession:
        session = RuntimeSession(session_id=f"session_{uuid4().hex}", context=context)
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> RuntimeSession:
        with self._lock:
            try:
                return self._sessions[session_id]
            except KeyError as exc:
                raise RuntimeException(f"Session not found: {session_id}") from exc

    def update_context(self, session_id: str, context: ExecutionContext) -> RuntimeSession:
        with self._lock:
            current = self.get(session_id)
            if current.is_closed:
                raise RuntimeException(f"Session is closed: {session_id}")
            updated = replace(current, context=context)
            self._sessions[session_id] = updated
            return updated

    def close(self, session_id: str) -> RuntimeSession:
        with self._lock:
            current = self.get(session_id)
            closed = current.close()
            self._sessions[session_id] = closed
            return closed

