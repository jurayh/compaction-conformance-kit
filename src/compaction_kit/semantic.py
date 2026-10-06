"""Semantic update resolution for checklist-style compaction.

The plain checklist extractor depends on typed headers, and the
update-aware variant keys items by masking values in otherwise identical
text. Neither recognizes that two differently worded statements govern
the same item.

This module provides a small, dependency-free reference resolver. It
classifies governed statements by semantic domain and scope (for
example, spending limit/project or deadline/launch), retains only the
latest statement for each identity, and leaves distinct scopes alone.
It is intentionally a taxonomy-based reference implementation, not a
claim of general natural-language understanding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .canaries import CanaryType
from .compacted import CompactedContext
from .compactors import ChecklistCompactor, _render_checklist, _turns_to_text
from .session import Turn

_HEADERS = {
    "SAFETY RULE": CanaryType.SAFETY_RULE,
    "HARD CONSTRAINT": CanaryType.HARD_CONSTRAINT,
    "FACT": CanaryType.FACT,
    "GOAL STATE": CanaryType.GOAL_STATE,
    "USER PREFERENCE": CanaryType.USER_PREFERENCE,
}


@dataclass(frozen=True)
class SemanticItem:
    text: str
    canary_type: CanaryType
    key: tuple[str, str]
    order: int


def _clean_line(line: str) -> str:
    text = line.strip()
    text = re.sub(r"^\[(system|user|assistant|tool)\]\s*", "", text, flags=re.I)
    text = re.sub(r"^[-*]\s+", "", text)
    return text.strip()


def _header_type(text: str) -> CanaryType | None:
    for header, ctype in _HEADERS.items():
        if header in text.upper():
            return ctype
    return None


def _has(text: str, *terms: str) -> bool:
    """Whole-token/phrase matching.

    Substring matching is too dangerous here: "capped" is not a budget
    cap, and "encode" is not a protected code. Terms are compared as
    token sequences, with spaces and hyphens treated equivalently.
    """
    for term in terms:
        tokens = re.findall(r"[a-z0-9]+", term.lower())
        if not tokens:
            continue
        pattern = r"(?<![a-z0-9])" + r"[\s-]+".join(map(re.escape, tokens)) + r"(?![a-z0-9])"
        if re.search(pattern, text):
            return True
    return False


def _scope(text: str, aliases: dict[str, tuple[str, ...]], default: str = "general") -> str:
    for canonical, terms in aliases.items():
        if _has(text, *terms):
            return canonical
    return default


def semantic_key(text: str) -> tuple[str, str] | None:
    """Return (domain, scope) for a governed statement, else None."""
    low = f" {text.lower()} "

    if _has(low, "code") and _has(low, "vault", "access", "maintenance", "staging", "login"):
        # An "access code" keeps that identity when a later rotation omits
        # a location qualifier such as "maintenance". Other code objects
        # retain their explicit qualifier.
        if _has(low, "access"):
            return ("protected_code", "access")
        scope = _scope(low, {
            "vault": ("vault",),
            "maintenance": ("maintenance",),
            "staging": ("staging",),
        })
        return ("protected_code", scope)

    if _has(low, "codename", "internal label", "calling the project", "project is called") or (
        _has(low, "designated") and _has(low, "project", "effort")
    ):
        return ("project_codename", "project")

    if _has(low, "branch", "rebased", "checked out") or (
        _has(low, "switched") and _has(low, "development", "branch")
    ):
        return ("working_branch", "current")

    if _has(low, "utc", "pacific time", "central time", "eastern time", "time zone", "timezone") or (
        _has(low, "timestamp", "clocks") and _has(low, "report", "show", "put", "use")
    ):
        return ("reporting_timezone", "reporting")

    if _has(low, "budget", "spend", "spending", "expense", "expenses", "cost", "costs", "ceiling", "cap") or re.search(r"\$\s*\d", low):
        scope = _scope(low, {
            "project": ("project",),
            "travel": ("travel", "trip", "field-trip", "field trip"),
            "conference": ("conference",),
            "team": ("team",),
            "product": ("product",),
        })
        return ("spending_limit", scope)

    if _has(low, "deadline", "due date", "target date", "launch date", "release timing", "date moved", "ship on", "scheduled for", "freeze") or (
        _has(low, "launch", "documentation", "docs", "release") and re.search(r"\b\d{4}-\d{2}-\d{2}\b|\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", low)
    ):
        scope = _scope(low, {
            "launch": ("launch",),
            "docs": ("docs", "documentation", "handbook"),
            "release": ("release",),
            "product": ("product",),
            "marketing": ("marketing",),
        })
        return ("deadline", scope)

    if _has(low, "pager", "on-call", "on call", "incident", "escalation", "support duty", "support escalation"):
        scope = _scope(low, {
            "support": ("support", "incident", "escalation"),
            "release": ("release",),
            "design": ("design",),
        })
        return ("incident_owner", scope)

    if _has(low, "design reviewer"):
        return ("design_reviewer", "design")
    if _has(low, "release approver"):
        return ("release_approver", "release")
    if _has(low, "reviewer", "approver") and _has(low, "week", "owner", "is", "belongs"):
        scope = _scope(low, {"design": ("design",), "release": ("release",)})
        return ("review_owner", scope)

    if _has(low, "answers", "responses", "replies", "answer style", "response style") and _has(
        low, "terse", "playful", "warm", "formal", "metric", "imperial", "style", "light", "measurements", "units"
    ):
        return ("response_style", "response")

    return None


def _infer_type(text: str, key: tuple[str, str]) -> CanaryType:
    typed = _header_type(text)
    if typed is not None:
        return typed
    domain = key[0]
    if domain == "protected_code":
        return CanaryType.SAFETY_RULE
    if domain in {"spending_limit", "reporting_timezone"}:
        return CanaryType.HARD_CONSTRAINT
    if domain == "working_branch":
        return CanaryType.GOAL_STATE
    if domain == "response_style":
        return CanaryType.USER_PREFERENCE
    return CanaryType.FACT


def extract_semantic_items(text: str) -> list[SemanticItem]:
    """Extract governed statements from transcript or compacted text."""
    items: list[SemanticItem] = []
    skip_prefixes = ("[compacted by", "preserved checklist")
    for order, raw in enumerate(text.splitlines()):
        clean = _clean_line(raw)
        if clean.lower().startswith("recent activity"):
            # The tail is a truncated duplicate of material already in the
            # transcript/checklist. Treating a mid-line tail fragment as a
            # later statement would let it supersede the complete item.
            break
        if not clean or clean.lower().startswith(skip_prefixes):
            continue
        if "?" in clean:
            # Questions and probe echoes mention a governed subject but do
            # not assert a value, so they must not supersede a statement.
            continue
        if re.fullmatch(r"\[(SAFETY_RULE|HARD_CONSTRAINT|FACT|GOAL_STATE|USER_PREFERENCE)\]", clean):
            continue
        key = semantic_key(clean)
        if key is None:
            continue
        items.append(SemanticItem(clean, _infer_type(clean, key), key, order))
    return items


def _normalized(text: str) -> str:
    return " ".join(text.lower().split()).strip(" -")


def _semantic_safe_tail(turns: list[Turn], tail_turns: int, max_chars: int = 800) -> str:
    """Recent context with governed statements removed.

    Governed statements are represented once, by their latest version, in
    the checklist. Copying the raw tail as well can reintroduce a stale
    statement that happens to fall inside the tail window.
    """
    lines: list[str] = []
    for turn in turns[-tail_turns:]:
        prefix_pending = True
        for raw in turn.text.splitlines():
            clean = _clean_line(raw)
            if not clean:
                continue
            if clean.lower().startswith("recent activity"):
                continue
            if clean.lower().startswith(("[compacted by", "preserved checklist")):
                continue
            if semantic_key(clean) is not None:
                continue
            content = raw.strip()
            if prefix_pending:
                content = f"[{turn.role}] {content}"
                prefix_pending = False
            lines.append(content)
    return "\n".join(lines)[-max_chars:]


class SemanticChecklistCompactor(ChecklistCompactor):
    """Checklist compaction with semantic update resolution.

    Governed statements are grouped by semantic identity (domain and
    scope), not by their literal wording. Only the latest statement in
    each group is carried. Typed items outside the semantic taxonomy
    continue through the ordinary checklist path.
    """

    name = "semantic-checklist"

    def compact(
        self, turns: list[Turn], round_num: int = 1, budget_chars: int | None = None
    ) -> CompactedContext:
        text = _turns_to_text(turns)
        semantic_items = extract_semantic_items(text)

        latest_by_key: dict[tuple[str, str], SemanticItem] = {}
        for item in semantic_items:
            latest_by_key[item.key] = item
        latest_norms = {_normalized(item.text) for item in latest_by_key.values()}
        superseded_norms = {
            _normalized(item.text) for item in semantic_items
        } - latest_norms

        sections: dict[str, list[str]] = {ctype.value: [] for ctype in CanaryType}
        raw_sections = self._extract(text)
        for ctype, items in raw_sections.items():
            for item in items:
                norm = _normalized(item)
                if norm in superseded_norms or norm in latest_norms:
                    continue
                if semantic_key(item) is not None:
                    continue
                if item not in sections[ctype]:
                    sections[ctype].append(item)

        for item in sorted(latest_by_key.values(), key=lambda x: x.order):
            bucket = sections[item.canary_type.value]
            if item.text not in bucket:
                bucket.append(item.text)

        tail = _semantic_safe_tail(turns, self.tail_turns) if turns else ""
        rendered, selected = _render_checklist(
            self.name,
            round_num,
            "PRESERVED CHECKLIST (semantic latest value wins):",
            sections,
            tail=tail,
            tail_heading="RECENT ACTIVITY (semantic statements held in checklist):",
            budget_chars=budget_chars,
        )
        return CompactedContext(
            text=rendered,
            compactor_name=self.name,
            round_num=round_num,
            structured=selected,
        )
