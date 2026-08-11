from __future__ import annotations


class RedotCompatError(Exception):
    """Base exception for expected tester failures."""


class ConfigurationError(RedotCompatError):
    """Raised when configuration is invalid or unsafe."""


class UnsafeArchiveError(RedotCompatError):
    """Raised before or during extraction when an archive violates policy."""


class SourceResolutionError(RedotCompatError):
    """Raised when a source cannot be resolved to immutable evidence."""


class CapabilityError(RedotCompatError):
    """Raised when an explicitly required runtime capability is unavailable."""


class EngineError(RedotCompatError):
    """Raised when an engine cannot be identified or fails a bounded doctor check."""


class HarnessProtocolError(RedotCompatError):
    """Raised when harness output cannot prove one ordered terminal result."""
