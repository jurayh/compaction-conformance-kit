import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit.benchmark import run_budget_benchmark
from compaction_kit.compacted import CompactedContext
from compaction_kit.compactors import (
    ChecklistCompactor,
    LLMSummarizerCompactor,
    LossyTruncationCompactor,
    NaiveSummaryCompactor,
    PinnedRulesCompactor,
    SummaryTailCompactor,
    UpdateAwareChecklistCompactor,
    _turns_to_text,
)
from compaction_kit.runner import run_conformance
from compaction_kit.semantic import SemanticChecklistCompactor
from compaction_kit.session import Turn, build_seeded_session

BUILT_INS = [
    LossyTruncationCompactor,
    NaiveSummaryCompactor,
    SummaryTailCompactor,
    PinnedRulesCompactor,
    ChecklistCompactor,
    UpdateAwareChecklistCompactor,
    SemanticChecklistCompactor,
]


class OldStyleCompactor:
    name = "old-style"

    def compact(self, turns, round_num=1):
        return CompactedContext(
            text="x" * 5000, compactor_name=self.name, round_num=round_num
        )


class BudgetAwareCompactor:
    name = "budget-aware"

    def __init__(self):
        self.budgets = []

    def compact(self, turns, round_num=1, budget_chars=None):
        self.budgets.append(budget_chars)
        return CompactedContext(
            text="short", compactor_name=self.name, round_num=round_num
        )


def test_old_style_compactor_still_runs_and_is_marked_noncompliant():
    run = run_conformance(
        build_seeded_session(), OldStyleCompactor(), rounds=2, budget_fraction=0.20
    )
    assert [r.within_budget for r in run.rounds] == [False, False]
    assert all(r.budget_chars for r in run.rounds)


def test_budget_is_fixed_across_rounds_and_passed_to_aware_compactors():
    session = build_seeded_session()
    compactor = BudgetAwareCompactor()
    run = run_conformance(session, compactor, rounds=3, budget_fraction=0.20)
    expected = int(len(_turns_to_text(session.transcript())) * 0.20)
    assert compactor.budgets == [expected, expected, expected]
    assert [r.budget_chars for r in run.rounds] == [expected] * 3
    assert all(r.within_budget for r in run.rounds)


def test_conflicting_budget_arguments_are_rejected():
    try:
        run_conformance(
            build_seeded_session(),
            ChecklistCompactor(),
            rounds=1,
            budget_chars=100,
            budget_fraction=0.20,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_all_built_ins_comply_at_standard_budgets():
    session = build_seeded_session()
    for cls in BUILT_INS:
        for fraction in (0.10, 0.20, 0.30):
            run = run_conformance(
                session, cls(), rounds=5, budget_fraction=fraction
            )
            assert all(r.within_budget for r in run.rounds), (
                cls.__name__,
                fraction,
                [(r.output_chars, r.budget_chars) for r in run.rounds],
            )


def test_tight_budget_checklist_prioritizes_safety_over_preferences():
    run = run_conformance(
        build_seeded_session(), ChecklistCompactor(), rounds=5, budget_fraction=0.10
    )
    final = run.rounds[-1]
    assert final.survival_by_type["safety_rule"] == 1.0
    assert final.survival_by_type["user_preference"] == 0.0


def test_llm_adapter_passes_budget_instruction_and_fits_output():
    seen = []

    def summarize(text):
        seen.append(text)
        return "word " * 1000

    compactor = LLMSummarizerCompactor(summarize)
    ctx = compactor.compact([Turn("user", "hello")], round_num=1, budget_chars=200)
    assert "at most 200 characters" in seen[0]
    assert len(ctx.text) <= 200


def test_budget_benchmark_ranks_semantic_first_at_30_percent():
    payload = run_budget_benchmark(
        {
            "lossy-truncation": LossyTruncationCompactor,
            "semantic-checklist": SemanticChecklistCompactor,
        },
        budgets=[0.30],
        seeds=[1],
        rounds=5,
    )
    entries = payload["entries"]
    assert entries[0]["compactor"] == "semantic-checklist"
    assert entries[0]["rank"] == 1
    assert entries[0]["budget_compliant"] is True
    assert entries[0]["semantic"]["resolved_rate"] == 1.0
    assert entries[1]["randomized"]["overall_final_survival"] == 0.0
