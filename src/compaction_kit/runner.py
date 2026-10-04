from __future__ import annotations

from dataclasses import dataclass, field

from .canaries import Canary, CanaryType, seeded_canaries
from .compactors import Compactor
from .compacted import CompactedContext
from .probes import BehaviorProbe
from .session import SeededSession, Turn


@dataclass
class RoundResult:
    round_num: int
    compactor_name: str
    # per-type survival rate 0..1
    survival_by_type: dict[str, float]
    # canary_id -> survived
    survived: dict[str, bool]
    context: CompactedContext


@dataclass
class ConformanceRun:
    compactor_name: str
    rounds: list[RoundResult] = field(default_factory=list)

    def survival_curve(self, canary_type: CanaryType) -> list[float]:
        return [r.survival_by_type.get(canary_type.value, 0.0) for r in self.rounds]


def _probe_all(canaries: list[Canary], text: str) -> dict[str, bool]:
    probe = BehaviorProbe()  # covers direct + behavior; direct-only canaries fall back
    return {c.id: probe.probe(c, text).survived for c in canaries}


def _rates(canaries: list[Canary], survived: dict[str, bool]) -> dict[str, float]:
    out: dict[str, float] = {}
    for ctype in CanaryType:
        group = [c for c in canaries if c.type == ctype]
        if group:
            out[ctype.value] = sum(1 for c in group if survived.get(c.id)) / len(group)
    return out


def run_conformance(
    session: SeededSession,
    compactor: Compactor,
    rounds: int = 5,
    canaries: list[Canary] | None = None,
) -> ConformanceRun:
    """Compact iteratively; after each round, probe the compacted context.

    Round k+1 compacts round k's output, which is what repeated /compact
    does in a long session.
    """
    canaries = canaries or seeded_canaries()
    run = ConformanceRun(compactor_name=compactor.name)
    turns: list[Turn] = session.transcript()
    for k in range(1, rounds + 1):
        ctx = compactor.compact(turns, round_num=k)
        survived = _probe_all(canaries, ctx.text)
        run.rounds.append(
            RoundResult(
                round_num=k,
                compactor_name=compactor.name,
                survival_by_type=_rates(canaries, survived),
                survived=survived,
                context=ctx,
            )
        )
        turns = [Turn("system", ctx.text)]
    return run
