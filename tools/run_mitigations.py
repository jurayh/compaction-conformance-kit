"""Mitigation comparison across the multi-seed corpus.

Scores every compactor (references plus mitigations) on two axes:
per-type survival across rounds, and supersession (latest held vs stale
carried). Writes examples/mitigations-results.json and prints a summary.
No canary values are printed.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit.compactors import (
    ChecklistCompactor,
    LossyTruncationCompactor,
    NaiveSummaryCompactor,
    PinnedRulesCompactor,
    SummaryTailCompactor,
    UpdateAwareChecklistCompactor,
)
from compaction_kit.corpus import build_random_session
from compaction_kit.report import build_report
from compaction_kit.runner import run_conformance

SEEDS = list(range(1, 13))
ROUNDS = 5
COMPACTORS = [
    LossyTruncationCompactor(),
    NaiveSummaryCompactor(),
    SummaryTailCompactor(),
    PinnedRulesCompactor(),
    ChecklistCompactor(),
    UpdateAwareChecklistCompactor(),
]


def _median(xs):
    return round(statistics.median(xs), 3) if xs else None


def main() -> None:
    payload = {"seeds": SEEDS, "rounds": ROUNDS, "by_compactor": {}}
    for compactor in COMPACTORS:
        r1 = defaultdict(list)
        r5 = defaultdict(list)
        cliffs = defaultdict(list)
        sup = defaultdict(lambda: {"n": 0, "latest": 0, "stale": 0, "both": 0, "stale_only": 0})
        for seed in SEEDS:
            session, canaries = build_random_session(seed)
            run = run_conformance(session, compactor, rounds=ROUNDS, canaries=canaries)
            report = build_report(run)
            for f in report.findings:
                r1[f.canary_type].append(f.round1_survival)
                r5[f.canary_type].append(f.final_survival)
                cliffs[f.canary_type].append(f.cliff_round)
            final_text = run.rounds[-1].context.text.lower()
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
        payload["by_compactor"][compactor.name] = {
            "round1_median_by_type": {t: _median(v) for t, v in sorted(r1.items())},
            "round5_median_by_type": {t: _median(v) for t, v in sorted(r5.items())},
            "cliff_rounds_by_type": {t: sorted({c for c in v if c is not None}) for t, v in sorted(cliffs.items())},
            "supersession": {k: dict(v) for k, v in sorted(sup.items())},
        }
        a = payload["by_compactor"][compactor.name]
        print(f"== {compactor.name} ==")
        print("  r1 median:", a["round1_median_by_type"])
        print("  r5 median:", a["round5_median_by_type"])
        print("  supersession:", a["supersession"])

    out = Path(__file__).resolve().parents[1] / "examples" / "mitigations-results.json"
    out.write_text(json.dumps(payload, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
