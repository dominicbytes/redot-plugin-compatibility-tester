"""Archive preflight and extraction."""

from redot_compat.archive.extract import extract_archive
from redot_compat.archive.safety import ArchiveSummary

__all__ = ["ArchiveSummary", "extract_archive"]
