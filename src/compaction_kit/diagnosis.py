"""Per-canary diagnosis: where a run lost what it lost.

The report says a type fell to 25%. The diagnosis says which canary
died, in which round, where it sat in the transcript, which required
tokens are missing from the final context, and whether a stale
superseded value is still being carried as current. That is the
difference between a score and a fix list.
"""

from __future__ import annotations

from dataclasses import dataclass

from .canaries import Canary
from .runner import ConformanceRun
from .session import SeededSession


@dataclass
class CanaryDiagnosis:
    canary_id: str
    canary_type: str
    position: str | None  # "early" | "middle" | "late" when known
    lost_round: int | None  # first round the canary was not held; None if held throughout
    held_final: bool
    missing_tokens: list[str]  # required tokens absent from the final context
    stale_tokens: list[str]  # superseded tokens still present in the final context

    @property
    def lost(self) -> bool:
        return self.lost_round is not None


def _bucket(index: int, total: int) -> str:
    frac = index / max(total, 1)
    if frac < 1 / 3:
        return "early"
    if frac < 2 / 3:
        return "middle"
    return "late"


def diagnose_run(
    run: ConformanceRun,
    canaries: list[Canary],
    session: SeededSession | None = None,
) -> list[CanaryDiagnosis]:
    if not run.rounds:
        return []
    final_text = run.rounds[-1].context.text.lower()
    positions = session.canary_positions if session is not None else {}
    total_turns = len(session.turns) if session is not None else 0
    diagnoses = []
    for canary in canaries:
        lost_round = None
        for round_result in run.rounds:
            if not round_result.survived.get(canary.id, False):
                lost_round = round_result.round_num
                break
        diagnoses.append(CanaryDiagnosis(
            canary_id=canary.id,
            canary_type=canary.type.value,
            position=(
                _bucket(positions[canary.id], total_turns)
                if canary.id in positions
                else None
            ),
            lost_round=lost_round,
            held_final=bool(run.rounds[-1].survived.get(canary.id, False)),
            missing_tokens=[
                token for token in canary.required_tokens
                if token.lower() not in final_text
            ],
            stale_tokens=[
                token for token in canary.superseded_tokens
                if token.lower() in final_text
            ],
        ))
    return diagnoses


def diagnosis_to_markdown(diagnoses: list[CanaryDiagnosis]) -> list[str]:
    """Markdown lines for the report's Diagnosis section."""
    problems = [d for d in diagnoses if d.lost or d.stale_tokens]
    lines = ["", "## Diagnosis", ""]
    if not problems:
        lines.append("All canaries held through the final round; no stale values carried.")
        return lines
    lines += [
        "| Canary | Type | Position | Lost at round | Missing from final context | Stale still present |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for d in problems:
        lost = str(d.lost_round) if d.lost_round is not None else "—"
        missing = ", ".join(d.missing_tokens) if d.missing_tokens else "—"
        stale = ", ".join(d.stale_tokens) if d.stale_tokens else "—"
        lines.append(
            f"| {d.canary_id} | {d.canary_type} | {d.position or '—'} | "
            f"{lost} | {missing} | {stale} |"
        )
    return lines
