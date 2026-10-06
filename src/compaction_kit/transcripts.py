"""Score compaction produced outside this kit.

Two entry points:

- `load_transcript(path)` reads a transcript produced by another
  system: JSONL with one {"role", "content"} (or "text") object per
  line, a JSON list of the same, or plain text with `[role] text` /
  `role: text` lines.
- `score_compacted_output(text, canaries)` probes externally produced
  compacted text against known canaries and returns the standard
  conformance report. The kit does not need to run the compactor;
  bring the output, get the score.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .canaries import Canary, CanaryType
from .compacted import CompactedContext
from .report import ConformanceReport, build_report
from .runner import ConformanceRun, RoundResult, _probe_all, _rates
from .session import Turn

_ROLE_LINE = re.compile(r"^\[?(system|user|assistant|tool)\]?\s*[:\]]\s*(.*)$", re.I)


def load_transcript(path: str | Path) -> list[Turn]:
    raw = Path(path).read_text()
    suffix = Path(path).suffix.lower()
    if suffix == ".jsonl":
        turns = []
        for line in raw.splitlines():
            line = line.strip()
            if line:
                turns.append(_turn_from_obj(json.loads(line)))
        return turns
    if suffix == ".json":
        data = json.loads(raw)
        if isinstance(data, dict):
            data = data.get("turns", [])
        return [_turn_from_obj(obj) for obj in data]
    turns = []
    for line in raw.splitlines():
        match = _ROLE_LINE.match(line.strip())
        if match:
            turns.append(Turn(match.group(1).lower(), match.group(2)))
        elif line.strip():
            turns.append(Turn("user", line.strip()))
    return turns


def _turn_from_obj(obj: dict) -> Turn:
    role = str(obj.get("role", "user")).lower()
    text = obj.get("content", obj.get("text", ""))
    return Turn(role, str(text))


def load_canaries(path: str | Path) -> list[Canary]:
    """Load canary definitions from a JSON list.

    Each entry: {"id", "type", "content", "required_tokens",
    "direct_question"}; "type" is one of the CanaryType values.
    Optional: "superseded_tokens", "behavior_scenario",
    "behavior_required_tokens", "exact_use_scenario",
    "exact_use_required_tokens".
    """
    data = json.loads(Path(path).read_text())
    canaries = []
    for obj in data:
        canaries.append(Canary(
            id=obj["id"],
            type=CanaryType(obj["type"]),
            content=obj["content"],
            required_tokens=tuple(obj["required_tokens"]),
            direct_question=obj.get("direct_question", ""),
            superseded_tokens=tuple(obj.get("superseded_tokens", ())),
            behavior_scenario=obj.get("behavior_scenario") or "",
            behavior_required_tokens=tuple(obj.get("behavior_required_tokens", ())),
            exact_use_scenario=obj.get("exact_use_scenario") or "",
            exact_use_required_tokens=tuple(obj.get("exact_use_required_tokens", ())),
        ))
    return canaries


def score_compacted_output(
    compacted_text: str,
    canaries: list[Canary],
    compactor_name: str = "external",
) -> ConformanceReport:
    """Probe one externally produced compacted context and report."""
    survived = _probe_all(canaries, compacted_text)
    run = ConformanceRun(compactor_name=compactor_name)
    run.rounds.append(RoundResult(
        round_num=1,
        compactor_name=compactor_name,
        survival_by_type=_rates(canaries, survived),
        survived=survived,
        context=CompactedContext(
            text=compacted_text, compactor_name=compactor_name, round_num=1
        ),
        input_chars=0,
        output_chars=len(compacted_text),
    ))
    report = build_report(run)
    # A custom canary set may cover only some types; absent types are
    # not failures and must not be flagged.
    present = {canary.type.value for canary in canaries}
    report.findings = [f for f in report.findings if f.canary_type in present]
    return report
