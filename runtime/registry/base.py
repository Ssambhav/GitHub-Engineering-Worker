"""Generic metadata registry."""

from __future__ import annotations

from collections.abc import Iterable
from threading import RLock
from typing import Generic, TypeVar

from runtime.exceptions import RegistryException

MetadataT = TypeVar("MetadataT")


class InMemoryRegistry(Generic[MetadataT]):
    """Thread-safe registry for metadata and optional implementations."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._lock = RLock()
        self._metadata: dict[str, MetadataT] = {}
        self._implementations: dict[str, object] = {}

    def register(self, metadata: MetadataT, implementation: object | None = None) -> None:
        identifier = getattr(metadata, "identifier", None)
        version = getattr(metadata, "version", None)
        if not identifier or not version:
            raise RegistryException(f"{self.kind} metadata must include identifier and version")
        with self._lock:
            if identifier in self._metadata:
                raise RegistryException(f"{self.kind} already registered: {identifier}")
            self._metadata[str(identifier)] = metadata
            if implementation is not None:
                self._implementations[str(identifier)] = implementation

    def get(self, identifier: str) -> MetadataT:
        with self._lock:
            try:
                return self._metadata[identifier]
            except KeyError as exc:
                raise RegistryException(f"{self.kind} not registered: {identifier}") from exc

    def get_implementation(self, identifier: str) -> object:
        with self._lock:
            try:
                return self._implementations[identifier]
            except KeyError as exc:
                raise RegistryException(f"{self.kind} implementation not registered: {identifier}") from exc

    def discover(self, *, capability: str | None = None) -> Iterable[MetadataT]:
        with self._lock:
            values = tuple(self._metadata.values())
        if capability is None:
            return values
        return tuple(
            item
            for item in values
            if capability in tuple(getattr(item, "capabilities", ()))
        )

    def contains(self, identifier: str) -> bool:
        with self._lock:
            return identifier in self._metadata

