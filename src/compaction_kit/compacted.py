from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompactedContext:
    """Output of one compaction round. Framework-agnostic.

    `text` is what the agent would see after compaction.
    `structured` optionally carries extracted sections a compactor kept.
    """

    text: str
    compactor_name: str
    round_num: int = 1
    structured: dict[str, list[str]] | None = None

    def as_transcript_text(self) -> str:
        return self.text
