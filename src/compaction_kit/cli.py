"""Command-line interface for the compaction conformance kit.

Commands:
  demo    seeded session through the built-in compactors (always exits 0)
  report  one compactor on the seeded session; exit 1 if any type is
          flagged at round 1 or hits a late cliff, else 0
  corpus  randomized multi-seed corpus run, aggregated as JSON
  benchmark  fixed-budget leaderboard across randomized and semantic suites

No API key, no model calls.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict

from .compactors import (
    ChecklistCompactor,
    LossyTruncationCompactor,
    NaiveSummaryCompactor,
    PinnedRulesCompactor,
    SummaryTailCompactor,
    UpdateAwareChecklistCompactor,
)
from .benchmark import budget_benchmark_to_markdown, run_budget_benchmark
from .corpus import build_random_session
from .report import build_report
from .runner import run_conformance
from .semantic import SemanticChecklistCompactor
from .session import build_seeded_session

COMPACTORS = {
    "lossy-truncation": LossyTruncationCompactor,
    "naive-summary": NaiveSummaryCompactor,
    "summary-plus-tail": SummaryTailCompactor,
    "pinned-rules": PinnedRulesCompactor,
    "checklist-carrying": ChecklistCompactor,
    "update-aware-checklist": UpdateAwareChecklistCompactor,
    "semantic-checklist": SemanticChecklistCompactor,
}


def _parse_seeds(spec: str) -> list[int]:
    seeds: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            seeds.extend(range(int(a), int(b) + 1))
        else:
            seeds.append(int(part))
    return seeds or [1]


def _cmd_demo(args) -> int:
    session = build_seeded_session()
    names = list(COMPACTORS) if args.compactor == "all" else [args.compactor]
    payload = {}
    for name in names:
        run = run_conformance(session, COMPACTORS[name](), rounds=args.rounds)
        report = build_report(run)
        payload[name] = report.to_dict()
        if args.format == "md":
            print(report.to_markdown())
    if args.format == "json":
        print(json.dumps(payload, indent=2))
    return 0


def _cmd_report(args) -> int:
    session = build_seeded_session()
    run = run_conformance(session, COMPACTORS[args.compactor](), rounds=args.rounds)
    report = build_report(run)
    if args.format == "json":
        print(report.to_json())
    else:
        print(report.to_markdown())
    return 1 if (report.flagged_types or report.late_cliff_types) else 0


def _cmd_corpus(args) -> int:
    seeds = _parse_seeds(args.seeds)
    names = list(COMPACTORS) if args.compactor == "all" else [args.compactor]
    out: dict = {"seeds": seeds, "rounds": args.rounds, "by_compactor": {}}
    for name in names:
        r1: dict[str, list[float]] = defaultdict(list)
        r5: dict[str, list[float]] = defaultdict(list)
        sup: dict[str, dict[str, int]] = defaultdict(
            lambda: {"n": 0, "latest": 0, "stale": 0, "both": 0, "stale_only": 0}
        )
        for seed in seeds:
            session, canaries = build_random_session(seed)
            run = run_conformance(session, COMPACTORS[name](), rounds=args.rounds, canaries=canaries)
            report = build_report(run)
            for f in report.findings:
                r1[f.canary_type].append(f.round1_survival)
                r5[f.canary_type].append(f.final_survival)
            final_text = run.rounds[-1].context.text.lower() if run.rounds else ""
            for c in canaries:
                if c.superseded_tokens:
                    latest = all(t.lower() in final_text for t in c.required_tokens)
                    stale = any(t.lower() in final_text for t in c.superseded_tokens)
                    d = sup[c.id]
                    d["n"] += 1
                    d["latest"] += int(latest)
                    d["stale"] += int(stale)
                    d["both"] += int(latest and stale)
                    d["stale_only"] += int(stale and not latest)
        out["by_compactor"][name] = {
            "round1_median_by_type": {t: round(statistics.median(v), 3) for t, v in sorted(r1.items())},
            "final_median_by_type": {t: round(statistics.median(v), 3) for t, v in sorted(r5.items())},
            "supersession": {k: dict(v) for k, v in sorted(sup.items())},
        }
    print(json.dumps(out, indent=2))
    return 0


def _parse_budgets(spec: str) -> list[float]:
    budgets = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        value = float(part[:-1]) / 100 if part.endswith("%") else float(part)
        if not (0 < value <= 1):
            raise ValueError(f"budget out of range: {part}")
        budgets.append(value)
    return budgets or [0.10, 0.20, 0.30]


def _cmd_benchmark(args) -> int:
    names = list(COMPACTORS) if args.compactor == "all" else [args.compactor]
    factories = {name: COMPACTORS[name] for name in names}
    payload = run_budget_benchmark(
        factories,
        budgets=_parse_budgets(args.budgets),
        seeds=_parse_seeds(args.seeds),
        rounds=args.rounds,
    )
    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(budget_benchmark_to_markdown(payload))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="compaction-kit", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="seeded session through built-in compactors")
    p_demo.add_argument("--compactor", choices=["all", *COMPACTORS], default="all")
    p_demo.add_argument("--rounds", type=int, default=5)
    p_demo.add_argument("--format", choices=["md", "json"], default="md")
    p_demo.set_defaults(fn=_cmd_demo)

    p_report = sub.add_parser("report", help="one compactor on the seeded session (CI exit codes)")
    p_report.add_argument("--compactor", choices=list(COMPACTORS), default="update-aware-checklist")
    p_report.add_argument("--rounds", type=int, default=5)
    p_report.add_argument("--format", choices=["md", "json"], default="md")
    p_report.set_defaults(fn=_cmd_report)

    p_corpus = sub.add_parser("corpus", help="randomized multi-seed corpus run (JSON)")
    p_corpus.add_argument("--compactor", choices=["all", *COMPACTORS], default="all")
    p_corpus.add_argument("--seeds", default="1-12", help="e.g. 1-12 or 1,3,5")
    p_corpus.add_argument("--rounds", type=int, default=5)
    p_corpus.set_defaults(fn=_cmd_corpus)

    p_benchmark = sub.add_parser(
        "benchmark", help="fixed-budget leaderboard (randomized + semantic suites)"
    )
    p_benchmark.add_argument("--compactor", choices=["all", *COMPACTORS], default="all")
    p_benchmark.add_argument("--budgets", default="0.10,0.20,0.30", help="fractions or percents, e.g. 0.1,0.2 or 10%,20%")
    p_benchmark.add_argument("--seeds", default="1-4", help="e.g. 1-4 or 1,3,5")
    p_benchmark.add_argument("--rounds", type=int, default=5)
    p_benchmark.add_argument("--format", choices=["md", "json"], default="md")
    p_benchmark.set_defaults(fn=_cmd_benchmark)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
