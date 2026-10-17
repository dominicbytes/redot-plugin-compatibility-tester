from __future__ import annotations


class RedotCompatError(Exception):
    """Base exception for expected tester failures."""


class ConfigurationError(RedotCompatError):
    """Raised when configuration is invalid or unsafe."""


class UnsafeArchiveError(RedotCompatError):
    """Raised before or during extraction when an archive violates policy."""


class SourceResolutionError(RedotCompatError):
    """Raised when a source cannot be resolved to immutable evidence."""


class EngineError(RedotCompatError):
    """Raised when an engine cannot be identified or fails a bounded doctor check."""


class HarnessProtocolError(RedotCompatError):
    """Raised when harness output cannot prove one ordered terminal result."""


class WorkerOutputError(RedotCompatError):
    """Raised when a file written by the untrusted worker violates read policy."""
