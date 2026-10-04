from __future__ import annotations

import re
from typing import Protocol

from .canaries import CanaryType, seeded_canaries
from .compacted import CompactedContext
from .session import Turn

_TYPE_HEADERS = {
    CanaryType.SAFETY_RULE: "SAFETY RULE",
    CanaryType.HARD_CONSTRAINT: "HARD CONSTRAINT",
    CanaryType.FACT: "FACT",
    CanaryType.GOAL_STATE: "GOAL STATE",
    CanaryType.USER_PREFERENCE: "USER PREFERENCE",
}


class Compactor(Protocol):
    name: str

    def compact(self, turns: list[Turn], round_num: int = 1) -> CompactedContext: ...


def _turns_to_text(turns: list[Turn]) -> str:
    return "\n".join(f"[{t.role}] {t.text}" for t in turns)


def _text_to_turns(text: str) -> list[Turn]:
    return [Turn("system", text)]


class LossyTruncationCompactor:
    """Naive truncation: keep only the tail of the transcript.

    Models the failure the motivating measurement reports: early-planted
    rules fall off the end and never come back.
    """

    name = "lossy-truncation"

    def __init__(self, keep_fraction: float = 0.30) -> None:
        self.keep_fraction = keep_fraction

    def compact(self, turns: list[Turn], round_num: int = 1) -> CompactedContext:
        text = _turns_to_text(turns)
        keep = max(1, int(len(text) * self.keep_fraction))
        tail = text[-keep:]
        # keep whole lines only
        tail = tail[tail.find("\n") + 1 :] if "\n" in tail else tail
        out = f"[compacted by {self.name} round {round_num}: truncated to last {self.keep_fraction:.0%}]\n{tail}"
        return CompactedContext(text=out, compactor_name=self.name, round_num=round_num)


class NaiveSummaryCompactor:
    """Simulated LLM summarizer with no structure.

    Summarizes fluently but drops specifics from early turns, the way a
    free-form summary does. Deterministic stand-in for the spike; a real
    LLM adapter implements the same Compactor protocol.
    """

    name = "naive-summary"

    def compact(self, turns: list[Turn], round_num: int = 1) -> CompactedContext:
        # summarize only the second half in any detail; first half collapses
        mid = len(turns) // 2
        early, late = turns[:mid], turns[mid:]
        late_text = _turns_to_text(late)
        summary = (
            f"[compacted by {self.name} round {round_num}]\n"
            "Earlier in the session the user set up a project and discussed "
            "pipeline layout, caching, tests, and assorted configuration. "
            "Several rules and preferences were mentioned during setup.\n"
            "Recent activity (verbatim tail):\n"
            f"{late_text[-1500:]}"
        )
        return CompactedContext(text=summary, compactor_name=self.name, round_num=round_num)


class LLMSummarizerCompactor:
    """LLM-driven summarizer adapter.

    The protocol does not depend on any particular model. Pass any callable
    `summarize(text) -> text` — e.g. a small model call:

        def summarize(text):
            return call_model("Summarize, preserving rules and facts:", text)

    For the spike no API key is required; NaiveSummaryCompactor is the
    deterministic stand-in. This adapter exists so a real /compact-style
    implementation can be dropped in without changing probes or reports.
    """

    name = "llm-summarizer"

    def __init__(self, summarize_fn, name: str = "llm-summarizer") -> None:
        self._summarize = summarize_fn
        self.name = name

    def compact(self, turns: list[Turn], round_num: int = 1) -> CompactedContext:
        text = _turns_to_text(turns)
        out = self._summarize(text)
        return CompactedContext(text=str(out), compactor_name=self.name, round_num=round_num)


class ChecklistCompactor:
    """Structure-preserving: extract typed items into a checklist that is
    carried verbatim across rounds, plus a recent-activity tail.

    This is the ground-truth 'good' implementation the kit must rank above
    the lossy ones. Extraction is marker-based for the spike (canaries are
    planted with typed headers); a production version would use an
    extraction prompt with the same output schema.
    """

    name = "checklist-carrying"

    def __init__(self, tail_turns: int = 6) -> None:
        self.tail_turns = tail_turns
        self._headers = {v: k for k, v in _TYPE_HEADERS.items()}

    def _extract(self, text: str) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {t.value: [] for t in CanaryType}
        # also recover checklist sections from a previous round's output
        current: str | None = None
        for line in text.splitlines():
            m = re.match(r"\[(SAFETY_RULE|HARD_CONSTRAINT|FACT|GOAL_STATE|USER_PREFERENCE)\]", line)
            if m:
                current = m.group(1)
                continue
            for header, ctype in self._headers.items():
                if header in line and ("[" in line or ":" in line):
                    # a planted canary line: keep the part from the header on
                    idx = line.find(header)
                    item = line[idx:].strip()
                    if item not in sections[ctype.value]:
                        sections[ctype.value].append(item)
                    current = None
                    break
            else:
                if current and line.strip().startswith("- "):
                    item = line.strip()[2:]
                    if item and item not in sections[current]:
                        sections[current].append(item)
        return sections

    def compact(self, turns: list[Turn], round_num: int = 1) -> CompactedContext:
        text = _turns_to_text(turns)
        sections = self._extract(text)
        # merge in any canonical canaries present verbatim (marker path)
        for c in seeded_canaries():
            if c.content.split(": ", 1)[-1].lower()[:24] in text.lower() or c.content in text:
                bucket = sections[c.type.value]
                if c.content not in bucket:
                    bucket.append(c.content)
        lines = [f"[compacted by {self.name} round {round_num}]", "PRESERVED CHECKLIST (carried verbatim):"]
        for ctype in CanaryType:
            lines.append(f"[{ctype.value}]")
            for item in sections[ctype.value]:
                lines.append(f"- {item}")
        tail = _turns_to_text(turns[-self.tail_turns :]) if turns else ""
        lines.append("RECENT ACTIVITY:")
        lines.append(tail[-800:])
        return CompactedContext(
            text="\n".join(lines),
            compactor_name=self.name,
            round_num=round_num,
            structured=sections,
        )


def _item_key(item: str) -> str:
    """Identity of a typed item with volatile values masked out.

    Two statements that differ only in a dollar amount, a date, or a short
    commit hash are the same item at different times; the later one wins.
    """
    key = item.lower()
    key = re.sub(r"\$\d[\d,]*", "$#", key)
    key = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "DATE", key)
    key = re.sub(r"\b[0-9a-f]{7}\b", "HASH", key)
    return " ".join(key.split())


class UpdateAwareChecklistCompactor(ChecklistCompactor):
    """Checklist carrying with update resolution: latest value wins.

    The plain checklist preserves everything, including values that were
    later superseded. This variant keys typed items with volatile values
    masked, so when the same item appears with a new cap or deadline,
    only the latest statement is carried.
    """

    name = "update-aware-checklist"

    def compact(self, turns: list[Turn], round_num: int = 1) -> CompactedContext:
        text = _turns_to_text(turns)
        raw = self._extract(text)
        sections: dict[str, list[str]] = {}
        for ctype, items in raw.items():
            latest: dict[str, str] = {}
            order: list[str] = []
            for item in items:
                k = _item_key(item)
                if k in latest:
                    order.remove(k)
                latest[k] = item
                order.append(k)
            sections[ctype] = [latest[k] for k in order]
        lines = [f"[compacted by {self.name} round {round_num}]", "PRESERVED CHECKLIST (latest value wins):"]
        for ctype in CanaryType:
            lines.append(f"[{ctype.value}]")
            for item in sections[ctype.value]:
                lines.append(f"- {item}")
        tail = _turns_to_text(turns[-self.tail_turns :]) if turns else ""
        lines.append("RECENT ACTIVITY:")
        lines.append(tail[-800:])
        return CompactedContext(
            text="\n".join(lines),
            compactor_name=self.name,
            round_num=round_num,
            structured=sections,
        )


class PinnedRulesCompactor:
    """Pin safety rules and hard constraints verbatim; summarize the rest.

    Models the common mitigation of keeping system-level rules outside
    the summarizer while everything else is compacted normally.
    """

    name = "pinned-rules"

    def __init__(self) -> None:
        self._extractor = ChecklistCompactor()
        self._summary = NaiveSummaryCompactor()

    def compact(self, turns: list[Turn], round_num: int = 1) -> CompactedContext:
        text = _turns_to_text(turns)
        sections = self._extractor._extract(text)
        pinned: list[str] = []
        for ctype in (CanaryType.SAFETY_RULE, CanaryType.HARD_CONSTRAINT):
            pinned.extend(sections[ctype.value])
        summary = self._summary.compact(turns, round_num=round_num).text
        lines = [f"[compacted by {self.name} round {round_num}]", "PINNED RULES (verbatim):"]
        lines.extend(f"- {item}" for item in pinned)
        lines.append("SUMMARY OF THE REST:")
        lines.append(summary)
        return CompactedContext(text="\n".join(lines), compactor_name=self.name, round_num=round_num)


class SummaryTailCompactor:
    """Free-form summary plus a verbatim recent tail.

    Models the hybrid used by several products: summarize the old
    context, keep the newest turns raw.
    """

    name = "summary-plus-tail"

    def __init__(self, keep_fraction: float = 0.30) -> None:
        self.keep_fraction = keep_fraction
        self._summary = NaiveSummaryCompactor()

    def compact(self, turns: list[Turn], round_num: int = 1) -> CompactedContext:
        text = _turns_to_text(turns)
        keep = max(1, int(len(text) * self.keep_fraction))
        tail = text[-keep:]
        tail = tail[tail.find("\n") + 1 :] if "\n" in tail else tail
        summary = self._summary.compact(turns, round_num=round_num).text
        out = f"[compacted by {self.name} round {round_num}]\n{summary}\nRAW TAIL:\n{tail}"
        return CompactedContext(text=out, compactor_name=self.name, round_num=round_num)
