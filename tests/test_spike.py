"""Kill-criterion tests for the compaction-conformance spike.

The kit is only worth building if it separates a lossy compaction from a
structure-preserving one. These tests encode that separation directly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit.canaries import CanaryType, seeded_canaries
from compaction_kit.compactors import ChecklistCompactor, LossyTruncationCompactor, NaiveSummaryCompactor
from compaction_kit.report import build_report
from compaction_kit.runner import run_conformance
from compaction_kit.session import build_seeded_session

SESSION = build_seeded_session()
ROUNDS = 5


def _run(compactor):
    return run_conformance(SESSION, compactor, rounds=ROUNDS)


def test_seeded_session_plants_every_canary():
    canaries = seeded_canaries()
    assert len(canaries) == 20
    assert {c.type for c in canaries} == set(CanaryType)
    for c in canaries:
        assert c.id in SESSION.canary_positions
        assert c.content in SESSION.full_text()


def test_lossy_is_flagged_after_round_1():
    report = build_report(_run(LossyTruncationCompactor()))
    assert report.flagged_types, "lossy compaction must be flagged on >=1 type"


def test_naive_summary_is_flagged_after_round_1():
    report = build_report(_run(NaiveSummaryCompactor()))
    assert report.flagged_types, "naive summary must be flagged on >=1 type"


def test_checklist_is_silent_after_round_1():
    report = build_report(_run(ChecklistCompactor()))
    assert report.silent_types, "checklist compaction must be silent somewhere"
    for f in report.findings:
        assert f.round1_survival > 0.90, f"{f.canary_type} at {f.round1_survival}"


def test_ordering_matches_ground_truth():
    good = _run(ChecklistCompactor())
    for bad in (_run(LossyTruncationCompactor()), _run(NaiveSummaryCompactor())):
        for ctype in CanaryType:
            g, b = good.survival_curve(ctype), bad.survival_curve(ctype)
            assert all(gv >= bv for gv, bv in zip(g, b)), (ctype, g, b)
        # strict overall separation
        g_all = [v for r in good.rounds for v in r.survival_by_type.values()]
        b_all = [v for r in bad.rounds for v in r.survival_by_type.values()]
        assert sum(g_all) > sum(b_all)


def test_survival_is_monotone_non_increasing_for_lossy():
    # once truncation drops a canary it never comes back
    run = _run(LossyTruncationCompactor())
    for ctype in CanaryType:
        curve = run.survival_curve(ctype)
        assert all(a >= b for a, b in zip(curve, curve[1:])), (ctype, curve)


def test_checklist_survives_all_rounds():
    run = _run(ChecklistCompactor())
    for r in run.rounds:
        for ctype, rate in r.survival_by_type.items():
            assert rate == 1.0, (r.round_num, ctype, rate)
