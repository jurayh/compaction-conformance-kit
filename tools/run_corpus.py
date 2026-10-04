"""Multi-seed corpus run: does the metric hold across random sessions?

For each seed, builds a randomized session, runs every reference
compactor for 5 rounds, and aggregates per-type survival, cliff rounds,
verdicts, position effects, and supersession handling. Writes
examples/corpus-results.json and prints a summary. No canary values are
printed.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit.compactors import ChecklistCompactor, LossyTruncationCompactor, NaiveSummaryCompactor
from compaction_kit.corpus import build_random_session, position_bucket
from compaction_kit.report import build_report
from compaction_kit.runner import run_conformance

SEEDS = list(range(1, 13))
ROUNDS = 5
COMPACTORS = [LossyTruncationCompactor(), NaiveSummaryCompactor(), ChecklistCompactor()]


def _median(xs):
    return round(statistics.median(xs), 3) if xs else None


def main() -> None:
    agg = {}
    position_survival = defaultdict(list)  # (compactor, bucket, round) -> [0/1 per canary]
    supersession = defaultdict(lambda: {"latest_held": 0, "stale_present": 0, "both_present": 0, "stale_only": 0, "n": 0})

    for compactor in COMPACTORS:
        per_type_r1 = defaultdict(list)
        per_type_r5 = defaultdict(list)
        cliffs = defaultdict(list)
        verdicts = defaultdict(lambda: defaultdict(int))
        for seed in SEEDS:
            session, canaries = build_random_session(seed)
            run = run_conformance(session, compactor, rounds=ROUNDS, canaries=canaries)
            report = build_report(run)
            by_id = {c.id: c for c in canaries}
            for f in report.findings:
                per_type_r1[f.canary_type].append(f.round1_survival)
                per_type_r5[f.canary_type].append(f.final_survival)
                cliffs[f.canary_type].append(f.cliff_round)
                verdicts[f.canary_type][f.verdict] += 1
            for r in run.rounds:
                for cid, held in r.survived.items():
                    bucket = position_bucket(session, cid)
                    position_survival[(compactor.name, bucket, r.round_num)].append(1 if held else 0)
            # supersession at final round: latest held? stale still present?
            final_text = run.rounds[-1].context.text.lower()
            for c in canaries:
                if c.superseded_tokens:
                    key = (compactor.name, c.id)
                    latest = all(t.lower() in final_text for t in c.required_tokens)
                    stale = any(t.lower() in final_text for t in c.superseded_tokens)
                    supersession[key]["n"] += 1
                    supersession[key]["latest_held"] += int(latest)
                    supersession[key]["stale_present"] += int(stale)
                    supersession[key]["both_present"] += int(latest and stale)
                    supersession[key]["stale_only"] += int(stale and not latest)

        agg[compactor.name] = {
            "round1_median_by_type": {t: _median(v) for t, v in sorted(per_type_r1.items())},
            "round5_median_by_type": {t: _median(v) for t, v in sorted(per_type_r5.items())},
            "round1_min_by_type": {t: min(v) for t, v in sorted(per_type_r1.items())},
            "cliff_rounds_by_type": {t: sorted({c for c in v if c is not None}) for t, v in sorted(cliffs.items())},
            "verdict_counts_by_type": {t: dict(v) for t, v in sorted(verdicts.items())},
        }

    pos = {}
    for (name, bucket, rnd), vals in sorted(position_survival.items()):
        if rnd in (1, 5):
            pos[f"{name}|{bucket}|r{rnd}"] = round(sum(vals) / len(vals), 3) if vals else None

    sup = {}
    for (name, cid), v in sorted(supersession.items()):
        sup[f"{name}|{cid}"] = {
            "sessions": v["n"],
            "latest_held": v["latest_held"],
            "stale_present": v["stale_present"],
            "both_present": v["both_present"],
            "stale_only": v["stale_only"],
        }

    payload = {"seeds": SEEDS, "rounds": ROUNDS, "by_compactor": agg, "position_survival": pos, "supersession": sup}
    out = Path(__file__).resolve().parents[1] / "examples" / "corpus-results.json"
    out.write_text(json.dumps(payload, indent=2))

    for name, a in agg.items():
        print(f"== {name} ==")
        print("  round1 median:", a["round1_median_by_type"])
        print("  round5 median:", a["round5_median_by_type"])
        print("  cliff rounds:", a["cliff_rounds_by_type"])
    print("position survival (r1/r5):", {k: v for k, v in pos.items()})
    print("supersession:", sup)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
