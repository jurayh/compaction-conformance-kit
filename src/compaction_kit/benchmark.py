"""Fixed-budget benchmark for compaction algorithms.

The conformance runner answers "what survived?" This module answers
the benchmark question: "what survived *at the same output budget*?"

Budgets are character caps, expressed as a fraction of the original
transcript. Characters are used because they are exact, deterministic,
and tokenizer-independent. The cap stays fixed across rounds: a 20%
budget means every round's output must fit in 20% of the original
transcript size, not 20% of the previous round.

A compactor declares budget support by accepting the optional
`budget_chars` keyword in `compact()`. Older two-argument compactors
still run; their outputs are measured and marked non-compliant when
they exceed the cap. Nothing is silently truncated by the benchmark.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from .canaries import CanaryType
from .compactors import Compactor, _turns_to_text
from .corpus import build_random_session
from .runner import run_conformance
from .semantic_corpus import build_semantic_heldout_session, build_semantic_session

DEFAULT_BUDGETS = (0.10, 0.20, 0.30)


@dataclass
class _RunStats:
    compliant: bool = True
    max_output_to_budget: float = 0.0
    final_output_ratios: list[float] = field(default_factory=list)


def _update_stats(stats: _RunStats, run, original_chars: int) -> None:
    for result in run.rounds:
        if not result.within_budget:
            stats.compliant = False
        if result.budget_chars:
            stats.max_output_to_budget = max(
                stats.max_output_to_budget,
                result.output_chars / result.budget_chars,
            )
    if run.rounds and original_chars:
        stats.final_output_ratios.append(run.rounds[-1].output_chars / original_chars)


def _session_chars(session) -> int:
    return len(_turns_to_text(session.transcript()))


def run_budget_benchmark(
    compactor_factories: Mapping[str, Callable[[], Compactor]],
    budgets: Sequence[float] = DEFAULT_BUDGETS,
    seeds: Sequence[int] = (1, 2, 3, 4),
    rounds: int = 5,
) -> dict:
    """Run the randomized and semantic suites at fixed output budgets."""
    entries: list[dict] = []
    for budget in budgets:
        if not (0 < budget <= 1):
            raise ValueError("budgets must be in (0, 1]")
        for name, factory in compactor_factories.items():
            started = time.perf_counter()
            stats = _RunStats()

            # Randomized corpus: preservation + re-stated update handling.
            type_curves: dict[str, list[float]] = {
                ctype.value: [] for ctype in CanaryType
            }
            survived_total = 0
            canary_total = 0
            sup = {"n": 0, "latest": 0, "resolved": 0, "stale": 0, "both": 0, "stale_only": 0}
            for seed in seeds:
                session, canaries = build_random_session(seed)
                run = run_conformance(
                    session,
                    factory(),
                    rounds=rounds,
                    canaries=canaries,
                    budget_fraction=budget,
                )
                _update_stats(stats, run, _session_chars(session))
                final = run.rounds[-1]
                for ctype, value in final.survival_by_type.items():
                    type_curves[ctype].append(value)
                survived_total += sum(final.survived.values())
                canary_total += len(canaries)
                text = final.context.text.lower()
                for canary in canaries:
                    if not canary.superseded_tokens:
                        continue
                    latest = all(t.lower() in text for t in canary.required_tokens)
                    stale = any(t.lower() in text for t in canary.superseded_tokens)
                    sup["n"] += 1
                    sup["latest"] += int(latest)
                    sup["resolved"] += int(latest and not stale)
                    sup["stale"] += int(stale)
                    sup["both"] += int(latest and stale)
                    sup["stale_only"] += int(stale and not latest)

            # Semantic corpora: paraphrased updates + false-merge control.
            sem = {
                "n": 0, "latest": 0, "resolved": 0, "stale": 0,
                "both": 0, "stale_only": 0, "pairs": 0, "pairs_both_held": 0,
            }
            for builder in (build_semantic_session, build_semantic_heldout_session):
                for seed in seeds:
                    session, canaries, meta = builder(seed)
                    run = run_conformance(
                        session,
                        factory(),
                        rounds=rounds,
                        canaries=canaries,
                        budget_fraction=budget,
                    )
                    _update_stats(stats, run, _session_chars(session))
                    final = run.rounds[-1]
                    text = final.context.text.lower()
                    for cid in meta["conflicts"]:
                        canary = next(item for item in canaries if item.id == cid)
                        latest = all(
                            t.lower() in text for t in canary.required_tokens
                        )
                        stale = any(
                            t.lower() in text for t in canary.superseded_tokens
                        )
                        sem["n"] += 1
                        sem["latest"] += int(latest)
                        sem["resolved"] += int(latest and not stale)
                        sem["stale"] += int(stale)
                        sem["both"] += int(latest and stale)
                        sem["stale_only"] += int(stale and not latest)
                    for first, second in meta["distinct_pairs"]:
                        sem["pairs"] += 1
                        sem["pairs_both_held"] += int(
                            bool(final.survived.get(first) and final.survived.get(second))
                        )

            entries.append({
                "compactor": name,
                "budget_fraction": budget,
                "budget_compliant": stats.compliant,
                "max_output_to_budget": round(stats.max_output_to_budget, 3),
                "mean_final_output_ratio": round(
                    statistics.mean(stats.final_output_ratios), 3
                ) if stats.final_output_ratios else 0.0,
                "runtime_seconds": round(time.perf_counter() - started, 3),
                "randomized": {
                    "sessions": len(seeds),
                    "overall_final_survival": round(
                        survived_total / canary_total, 3
                    ) if canary_total else 0.0,
                    "final_median_by_type": {
                        ctype: round(statistics.median(values), 3)
                        for ctype, values in sorted(type_curves.items())
                        if values
                    },
                    "supersession": sup,
                },
                "semantic": {
                    "sessions": len(seeds) * 2,
                    "conflicts": sem,
                    "resolved_rate": round(sem["resolved"] / sem["n"], 3) if sem["n"] else 0.0,
                    "distinct_pair_rate": round(
                        sem["pairs_both_held"] / sem["pairs"], 3
                    ) if sem["pairs"] else 0.0,
                },
            })

    # Rank inside each budget group. Compliance is a gate, then overall
    # preservation, semantic resolution, distinctness, and smaller output.
    # Preservation comes before resolution so a compactor that loses
    # almost everything cannot rank highly for resolving a few updates
    # by recency alone.
    for budget in budgets:
        group = [entry for entry in entries if entry["budget_fraction"] == budget]
        group.sort(key=lambda entry: (
            not entry["budget_compliant"],
            -entry["randomized"]["overall_final_survival"],
            -entry["semantic"]["resolved_rate"],
            -entry["semantic"]["distinct_pair_rate"],
            entry["mean_final_output_ratio"],
        ))
        for rank, entry in enumerate(group, start=1):
            entry["rank"] = rank

    entries.sort(key=lambda entry: (entry["budget_fraction"], entry["rank"]))
    return {
        "budgets": list(budgets),
        "seeds": list(seeds),
        "rounds": rounds,
        "budget_unit": "characters, fraction of original transcript, fixed across rounds",
        "entries": entries,
    }


def budget_benchmark_to_markdown(payload: dict) -> str:
    lines = [
        "# Budget benchmark",
        "",
        f"Budgets are {payload['budget_unit']}.",
        "Ranking gate: budget compliance first, then overall preservation, "
        "semantic resolution, distinct-pair preservation, and output size.",
        "",
    ]
    for budget in payload["budgets"]:
        lines += [
            f"## Budget {budget:.0%}",
            "",
            "| Rank | Compactor | Compliant | Survival | Semantic resolved | Stale present | Distinct pairs | Final output |",
            "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        group = [
            entry for entry in payload["entries"]
            if entry["budget_fraction"] == budget
        ]
        for entry in sorted(group, key=lambda item: item["rank"]):
            sem = entry["semantic"]["conflicts"]
            lines.append(
                f"| {entry['rank']} | {entry['compactor']} | "
                f"{'yes' if entry['budget_compliant'] else 'NO'} | "
                f"{entry['randomized']['overall_final_survival']:.1%} | "
                f"{entry['semantic']['resolved_rate']:.1%} | "
                f"{sem['stale']}/{sem['n']} | "
                f"{entry['semantic']['distinct_pair_rate']:.1%} | "
                f"{entry['mean_final_output_ratio']:.1%} |"
            )
        lines.append("")
    return "\n".join(lines)
