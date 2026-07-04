"""Structured logging contracts.

Runtime components depend on the StructuredLogger protocol from
runtime.interfaces. Concrete logging providers are intentionally supplied by
applications embedding the runtime.
"""

from runtime.interfaces import StructuredLogger

__all__ = ["StructuredLogger"]

