from __future__ import annotations

import inspect
from dataclasses import dataclass, field

from .canaries import Canary, CanaryType, seeded_canaries
from .compactors import Compactor, _turns_to_text
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
    input_chars: int = 0
    output_chars: int = 0
    budget_chars: int | None = None
    within_budget: bool = True

    @property
    def compression_ratio(self) -> float:
        """Output size as a fraction of the round's input size."""
        return self.output_chars / self.input_chars if self.input_chars else 0.0


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


def _call_compactor(
    compactor: Compactor,
    turns: list[Turn],
    round_num: int,
    budget_chars: int | None,
) -> CompactedContext:
    """Call a compactor, passing the budget only if its signature takes it.

    The original two-argument protocol remains valid: older custom
    compactors are called unchanged and are simply reported as
    non-compliant when their output exceeds the benchmark budget.
    """
    if budget_chars is not None:
        try:
            params = inspect.signature(compactor.compact).parameters
            accepts_budget = "budget_chars" in params or any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
            )
        except (TypeError, ValueError):
            accepts_budget = False
        if accepts_budget:
            return compactor.compact(turns, round_num=round_num, budget_chars=budget_chars)
    return compactor.compact(turns, round_num=round_num)


def run_conformance(
    session: SeededSession,
    compactor: Compactor,
    rounds: int = 5,
    canaries: list[Canary] | None = None,
    budget_chars: int | None = None,
    budget_fraction: float | None = None,
) -> ConformanceRun:
    """Compact iteratively; after each round, probe the compacted context.

    Round k+1 compacts round k's output, which is what repeated /compact
    does in a long session.

    A budget is an output-size cap in characters. `budget_fraction`
    expresses the cap as a fraction of the original transcript and stays
    fixed across rounds; it does not shrink round over round.
    """
    if budget_chars is not None and budget_fraction is not None:
        raise ValueError("pass only one of budget_chars and budget_fraction")
    if budget_fraction is not None and not (0 < budget_fraction <= 1):
        raise ValueError("budget_fraction must be in (0, 1]")
    canaries = canaries or seeded_canaries()
    run = ConformanceRun(compactor_name=compactor.name)
    turns: list[Turn] = session.transcript()
    original_chars = len(_turns_to_text(turns))
    effective_budget = budget_chars
    if budget_fraction is not None:
        effective_budget = max(1, int(original_chars * budget_fraction))
    for k in range(1, rounds + 1):
        input_chars = len(_turns_to_text(turns))
        ctx = _call_compactor(compactor, turns, k, effective_budget)
        survived = _probe_all(canaries, ctx.text)
        output_chars = len(ctx.text)
        run.rounds.append(
            RoundResult(
                round_num=k,
                compactor_name=compactor.name,
                survival_by_type=_rates(canaries, survived),
                survived=survived,
                context=ctx,
                input_chars=input_chars,
                output_chars=output_chars,
                budget_chars=effective_budget,
                within_budget=(
                    effective_budget is None or output_chars <= effective_budget
                ),
            )
        )
        turns = [Turn("system", ctx.text)]
    return run
