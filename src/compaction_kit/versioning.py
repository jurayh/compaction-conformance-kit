"""Schema versioning for the kit's JSON payloads.

Report JSON (`ConformanceReport.to_dict`) and benchmark JSON
(`run_budget_benchmark`) both carry `schema_version` and
`kit_version`, so saved artifacts say which format they use and
which kit produced them.

Compatibility policy: within a schema version, fields are only
added, never renamed, removed, or re-typed, and consumers must
ignore fields they do not know. A breaking change bumps
`SCHEMA_VERSION`. `diff` reads only `findings`, so it accepts
reports from any kit release, versioned or not.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

SCHEMA_VERSION = 1


def kit_version() -> str:
    """Installed kit version, or "unknown" from a bare source tree."""
    try:
        return version("compaction-conformance-kit")
    except PackageNotFoundError:
        return "unknown"
