import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit.benchmark import run_budget_benchmark
from compaction_kit.compactors import ChecklistCompactor, LossyTruncationCompactor
from compaction_kit.diffing import diff_reports
from compaction_kit.report import build_report
from compaction_kit.runner import run_conformance
from compaction_kit.session import build_seeded_session
from compaction_kit.testing import check_compactor
from compaction_kit.transcripts import score_compacted_output
from compaction_kit.versioning import SCHEMA_VERSION, kit_version

_SCHEMA_KEYS = ("schema_version", "kit_version", "rounds")


def _legacy(payload: dict) -> dict:
    """A pre-versioning payload: the new top-level keys stripped."""
    legacy = copy.deepcopy(payload)
    for key in _SCHEMA_KEYS:
        legacy.pop(key, None)
    return legacy


def test_report_json_carries_schema_fields():
    report = check_compactor(ChecklistCompactor(), rounds=3)
    payload = report.to_dict()
    assert payload["schema_version"] == SCHEMA_VERSION == 1
    assert payload["kit_version"] == kit_version()
    assert isinstance(payload["kit_version"], str) and payload["kit_version"]
    assert payload["rounds"] == 3
    assert report.rounds == 3
    # the pre-existing fields are untouched
    assert payload["compactor"] == "checklist-carrying"
    assert payload["thresholds"] == {"flag_below": 0.5, "silent_above": 0.9}
    assert len(payload["findings"]) == 5


def test_score_report_rounds_is_one():
    from compaction_kit.canaries import seeded_canaries

    canaries = seeded_canaries()
    session = build_seeded_session()
    compacted = ChecklistCompactor().compact(session.turns, round_num=1)
    report = score_compacted_output(compacted.text, canaries)
    payload = report.to_dict()
    assert payload["schema_version"] == 1
    assert payload["rounds"] == 1


def test_benchmark_json_carries_schema_fields():
    payload = run_budget_benchmark(
        {"checklist-carrying": ChecklistCompactor},
        budgets=[0.2], seeds=[1], rounds=1,
    )
    assert payload["schema_version"] == SCHEMA_VERSION == 1
    assert payload["kit_version"] == kit_version()
    assert payload["rounds"] == 1
    assert payload["budgets"] == [0.2]
    assert payload["entries"]


def test_diff_accepts_legacy_and_versioned_reports():
    session = build_seeded_session()
    good = build_report(run_conformance(session, ChecklistCompactor(), rounds=3)).to_dict()
    bad = build_report(
        run_conformance(session, LossyTruncationCompactor(), rounds=3)
    ).to_dict()

    # versioned vs versioned (the new normal)
    assert diff_reports(good, bad).has_regressions
    assert not diff_reports(bad, good).has_regressions
    # legacy baseline vs versioned current, and the reverse
    assert diff_reports(_legacy(good), bad).has_regressions
    assert diff_reports(good, _legacy(bad)).has_regressions
    assert not diff_reports(_legacy(bad), _legacy(good)).has_regressions
    # identical reports diff clean in both formats
    assert not diff_reports(good, copy.deepcopy(good)).has_regressions
    assert not diff_reports(_legacy(good), _legacy(good)).has_regressions


def test_markdown_and_html_do_not_leak_schema_fields():
    report = check_compactor(ChecklistCompactor(), rounds=1)
    assert "schema_version" not in report.to_markdown()
    assert "schema_version" not in report.to_html()
