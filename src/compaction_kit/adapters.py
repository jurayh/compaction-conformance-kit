"""External-pattern adapters.

Compactors that were not designed for this kit's canaries, included to
prove the protocol and the benchmark are neutral:

- `ProgressiveSummaryCompactor` implements the summary-buffer pattern
  popularized by LangChain's ConversationSummaryBufferMemory: a
  running summary of older turns plus a verbatim buffer of recent
  turns. When the buffer overflows, the oldest turns are folded into
  the summary. It knows nothing about canary types or checklists.
- `PrecomputedCompactor` replays a fixed compacted text produced
  elsewhere (a product's real /compact output, saved to a file), so
  externally produced compaction can be scored by the same probes.
"""

from __future__ import annotations

from collections.abc import Callable

from .compacted import CompactedContext
from .compactors import _truncate_to_budget, _turns_to_text
from .session import Turn

_SUMMARY_MARKER = "SUMMARY:"
_RECENT_MARKER = "RECENT TURNS:"


def _gist(parts: list[str], limit: int = 90) -> str:
    """Deterministic stand-in for an LLM gist call.

    Keeps the head of each folded turn, the way a short summary keeps
    topics and drops specifics. Pass your own `summarize_fn` to use a
    real model instead.
    """
    fragments = []
    for part in parts:
        part = " ".join(part.split())
        if part:
            fragments.append(part[:limit])
    return " / ".join(fragments)


class ProgressiveSummaryCompactor:
    """Summary-buffer compaction (LangChain-style), budget-aware.

    The output is a running summary plus the most recent turns kept
    verbatim, in the pattern of ConversationSummaryBufferMemory with
    the LLM replaced by a pluggable `summarize_fn`. On later rounds it
    re-reads its own SUMMARY / RECENT TURNS sections, folds buffer
    overflow into the summary, and continues — the way the real
    pattern behaves under repeated compaction.
    """

    name = "progressive-summary"

    def __init__(
        self,
        summarize_fn: Callable[[list[str]], str] | None = None,
        buffer_fraction: float = 0.5,
        max_chars: int = 2400,
        name: str = "progressive-summary",
    ) -> None:
        self._summarize = summarize_fn or _gist
        self.buffer_fraction = buffer_fraction
        self.max_chars = max_chars
        self.name = name

    def _parse(self, turns: list[Turn]) -> tuple[str, list[str]]:
        """Split input into (existing summary, turn strings)."""
        text = _turns_to_text(turns)
        if _SUMMARY_MARKER in text and _RECENT_MARKER in text:
            summary = text.split(_SUMMARY_MARKER, 1)[1].split(_RECENT_MARKER, 1)[0].strip()
            recent = text.split(_RECENT_MARKER, 1)[1]
            turn_strs = [
                line.strip()
                for line in recent.splitlines()
                if line.strip() and not line.startswith("[compacted by")
            ]
            return summary, turn_strs
        turn_strs = [
            f"[{t.role}] {t.text}"
            for t in turns
            if not t.text.startswith("[compacted by")
        ]
        return "", turn_strs

    def compact(
        self, turns: list[Turn], round_num: int = 1, budget_chars: int | None = None
    ) -> CompactedContext:
        summary, turn_strs = self._parse(turns)
        total = budget_chars if budget_chars is not None else self.max_chars
        header = f"[compacted by {self.name} round {round_num}]\n"
        overhead = len(header) + len(_SUMMARY_MARKER) + len(_RECENT_MARKER) + 3
        avail = max(0, total - overhead)
        buffer_budget = int(avail * self.buffer_fraction)
        summary_budget = avail - buffer_budget

        # Buffer: most recent turns, whole, from the end.
        buffer: list[str] = []
        used = 0
        for turn_str in reversed(turn_strs):
            cost = len(turn_str) + 1
            if buffer and used + cost > buffer_budget:
                break
            if not buffer and cost > buffer_budget:
                buffer.append(turn_str[-buffer_budget:] if buffer_budget else "")
                used = buffer_budget
                break
            buffer.append(turn_str)
            used += cost
        buffer.reverse()
        folded = turn_strs[: len(turn_strs) - len(buffer)]

        if folded or summary:
            parts = ([summary] if summary else []) + folded
            summary = self._summarize(parts)
        summary = _truncate_to_budget(summary, summary_budget)

        out = f"{header}{_SUMMARY_MARKER}\n{summary}\n{_RECENT_MARKER}\n" + "\n".join(buffer)
        out = _truncate_to_budget(out, total)
        return CompactedContext(text=out, compactor_name=self.name, round_num=round_num)


class PrecomputedCompactor:
    """Replay compacted text produced by an external system.

    The text is returned unchanged on every round, so a single real
    /compact output can be scored by the conformance runner and the
    budget benchmark. If a budget is supplied and the text exceeds it,
    the runner reports the output as non-compliant; the text is never
    altered.
    """

    def __init__(self, text: str, name: str = "precomputed") -> None:
        self._text = text
        self.name = name

    def compact(
        self, turns: list[Turn], round_num: int = 1, budget_chars: int | None = None
    ) -> CompactedContext:
        return CompactedContext(
            text=self._text, compactor_name=self.name, round_num=round_num
        )
