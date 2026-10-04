"""Spike CLI: seeded session through lossy vs structure-preserving compaction.

Kill criterion (all must hold, else the kit cannot separate implementations):
  1. Lossy compaction is FLAGged on at least one type after round 1 (<50%).
  2. Checklist compaction stays SILENT on every type after round 1 (>90%).
  3. Ordering matches ground truth: checklist survival >= lossy survival
     for every type at every round, with strict overall separation.

Usage:  python -m compaction_kit.spike [--rounds 5]
Writes reports under examples/ when run as a script.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compaction_kit.compactors import ChecklistCompactor, LossyTruncationCompactor, NaiveSummaryCompactor
from compaction_kit.report import build_report
from compaction_kit.runner import run_conformance
from compaction_kit.session import build_seeded_session


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()

    session = build_seeded_session()
    compactors = [LossyTruncationCompactor(), NaiveSummaryCompactor(), ChecklistCompactor()]
    runs = {c.name: run_conformance(session, c, rounds=args.rounds) for c in compactors}
    reports = {name: build_report(run) for name, run in runs.items()}

    for name, rep in reports.items():
        print(rep.to_markdown())

    lossy = reports["lossy-truncation"]
    naive = reports["naive-summary"]
    good = reports["checklist-carrying"]

    checks: dict[str, bool] = {}
    checks["lossy_flagged_at_least_one_type"] = len(lossy.flagged_types) >= 1
    checks["naive_flagged_at_least_one_type"] = len(naive.flagged_types) >= 1
    checks["checklist_silent_on_all_types"] = len(good.silent_types) == len(good.findings)
    # ordering: checklist >= both lossy variants per type per round, and strictly better overall
    ordering = True
    strict_somewhere = False
    for f_good in good.findings:
        for bad_rep in (lossy, naive):
            f_bad = next(f for f in bad_rep.findings if f.canary_type == f_good.canary_type)
            for g, b in zip(f_good.curve, f_bad.curve):
                if g < b:
                    ordering = False
                if g > b:
                    strict_somewhere = True
    checks["ordering_matches_ground_truth"] = ordering and strict_somewhere

    print("KILL CRITERION:")
    for k, v in checks.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    passed = all(checks.values())
    print(f"SPIKE: {'PASS' if passed else 'FAIL — kit cannot separate implementations, stop'}")

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        payload = {name: rep.to_dict() for name, rep in reports.items()}
        payload["_kill_criterion"] = checks
        (out / "spike-results.json").write_text(json.dumps(payload, indent=2))
        for name, rep in reports.items():
            (out / f"report-{name}.md").write_text(rep.to_markdown())
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
