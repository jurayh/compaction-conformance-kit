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
        for lineno, line in enumerate(raw.splitlines(), start=1):
            line = line.strip()
            if line:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}: line {lineno}: invalid JSON: {exc}") from exc
                turns.append(_turn_from_obj(obj))
        return turns
    if suffix == ".json":
        data = json.loads(raw)
        if isinstance(data, dict):
            if "turns" not in data:
                raise ValueError("JSON transcript object must have a 'turns' list")
            data = data["turns"]
        if not isinstance(data, list):
            raise ValueError("JSON transcript must be a list of turns")
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
    if not isinstance(obj, dict):
        raise ValueError(f"transcript turn must be an object, got {type(obj).__name__}")
    role = str(obj.get("role", "user")).lower()
    text = obj.get("content", obj.get("text", ""))
    return Turn(role, "" if text is None else str(text))


def _token_list(obj: dict, field: str, canary_id: str) -> tuple[str, ...]:
    value = obj.get(field, [])
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(
            f"canary {canary_id}: {field} must be a JSON list of strings, "
            f"got {type(value).__name__}"
        )
    return tuple(str(v) for v in value)


def load_canaries(path: str | Path) -> list[Canary]:
    """Load canary definitions from a JSON list.

    Each entry: {"id", "type", "content", "required_tokens",
    "direct_question"}; "type" is one of the CanaryType values.
    Optional: "superseded_tokens", "behavior_scenario",
    "behavior_required_tokens", "exact_use_scenario",
    "exact_use_required_tokens".
    """
    data = json.loads(Path(path).read_text())
    if not isinstance(data, list):
        raise ValueError("canary file must be a JSON list of canary objects")
    canaries = []
    for index, obj in enumerate(data):
        if not isinstance(obj, dict):
            raise ValueError(f"canary entry {index} must be an object")
        for field in ("id", "type", "content", "required_tokens"):
            if field not in obj:
                raise ValueError(f"canary entry {index} is missing field {field!r}")
        canaries.append(Canary(
            id=obj["id"],
            type=CanaryType(obj["type"]),
            content=obj["content"],
            required_tokens=_token_list(obj, "required_tokens", obj["id"]),
            direct_question=obj.get("direct_question", ""),
            superseded_tokens=_token_list(obj, "superseded_tokens", obj["id"]),
            behavior_scenario=obj.get("behavior_scenario") or "",
            behavior_required_tokens=_token_list(obj, "behavior_required_tokens", obj["id"]),
            exact_use_scenario=obj.get("exact_use_scenario") or "",
            exact_use_required_tokens=_token_list(obj, "exact_use_required_tokens", obj["id"]),
        ))
    return canaries


def score_compacted_output(
    compacted_text: str,
    canaries: list[Canary],
    compactor_name: str = "external",
) -> ConformanceReport:
    """Probe one externally produced compacted context and report."""
    if not canaries:
        raise ValueError("no canaries to score against")
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
    report = build_report(run, canaries=canaries)
    # A custom canary set may cover only some types; absent types are
    # not failures and must not be flagged.
    present = {canary.type.value for canary in canaries}
    report.findings = [f for f in report.findings if f.canary_type in present]
    return report
