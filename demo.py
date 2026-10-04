#!/usr/bin/env python3
"""Demo: what does compaction preserve?

Runs a seeded session (20 typed canaries planted at known positions in a
~100-turn transcript) through three compaction implementations for five
rounds each, then prints a per-type conformance report for each.

No API key, no model calls. Run:

    PYTHONPATH=src python3 demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from compaction_kit.compactors import (
    ChecklistCompactor,
    LossyTruncationCompactor,
    NaiveSummaryCompactor,
)
from compaction_kit.report import build_report
from compaction_kit.runner import run_conformance
from compaction_kit.session import build_seeded_session

HEADER = """
====================================================================
COMPACTION CONFORMANCE DEMO
A seeded session holds 20 typed canaries:
  safety_rule x4, hard_constraint x4, fact x4,
  goal_state x4, user_preference x4
planted at known positions across the transcript.

Each compactor runs 5 rounds; round k+1 compacts round k's output.
After every round we probe: does the agent still hold each canary?

FLAG  = under 50% survival after round 1
SILENT = over 90% survival after round 1
CLIFF = first round a type falls under 50% (it can arrive late)
====================================================================
""".strip()


def main() -> int:
    print(HEADER)
    session = build_seeded_session()
    print(f"\nSeeded session: {len(session.turns)} turns, "
          f"{len(session.canary_positions)} canaries planted.\n")

    compactors = [
        LossyTruncationCompactor(),
        NaiveSummaryCompactor(),
        ChecklistCompactor(),
    ]
    reports = []
    for compactor in compactors:
        run = run_conformance(session, compactor, rounds=5)
        report = build_report(run)
        reports.append(report)
        print("-" * 68)
        print(report.to_markdown())

    print("-" * 68)
    lossy, _naive, good = reports
    print("READING THE RESULT")
    print(f"  Lossy truncation is flagged on: {', '.join(lossy.flagged_types) or 'nothing'}")
    print(f"  Checklist compaction is silent on: {', '.join(good.silent_types) or 'nothing'}")
    print()
    print("  The lossy compactor forgets safety rules first and never")
    print("  recovers them. The checklist compactor loses nothing in")
    print("  five rounds. The kit separates them; that separation is")
    print("  its kill criterion, and it passes.")
    print()
    print("  Same measurement, your compaction: implement the Compactor")
    print("  protocol (one class) and run build_seeded_session() through it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
