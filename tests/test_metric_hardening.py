import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit.canaries import Canary, CanaryType, seeded_canaries
from compaction_kit.compacted import CompactedContext
from compaction_kit.compactors import ChecklistCompactor
from compaction_kit.probes import ExactUseProbe
from compaction_kit.report import build_report
from compaction_kit.runner import ConformanceRun, RoundResult, run_conformance
from compaction_kit.session import build_seeded_session
from compaction_kit.simulated_agent import SimulatedAgent


def test_late_cliff_is_reported_when_round_1_is_clean():
    # the free-form LLM shape: 100% for two rounds, then safety falls off
    curves = {t.value: [1.0] * 5 for t in CanaryType}
    curves[CanaryType.SAFETY_RULE.value] = [1.0, 1.0, 0.0, 0.0, 0.0]
    run = ConformanceRun(compactor_name="synthetic-free-form")
    for i in range(5):
        run.rounds.append(
            RoundResult(
                round_num=i + 1,
                compactor_name="synthetic-free-form",
                survival_by_type={k: v[i] for k, v in curves.items()},
                survived={},
                context=CompactedContext(text="", compactor_name="synthetic-free-form", round_num=i + 1),
            )
        )
    report = build_report(run)
    safety = next(f for f in report.findings if f.canary_type == "safety_rule")
    assert safety.verdict == "SILENT"  # round-1 gate alone would miss it
    assert safety.cliff_round == 3
    assert safety.final_survival == 0.0
    assert "safety_rule" in report.late_cliff_types


def test_checklist_has_no_cliff():
    run = run_conformance(build_seeded_session(), ChecklistCompactor(), rounds=5)
    report = build_report(run)
    assert report.cliff_types == []
    assert report.late_cliff_types == []


def test_exact_use_requires_the_value_not_generic_caution():
    canary = Canary(
        id="x-budget",
        type=CanaryType.HARD_CONSTRAINT,
        content="HARD CONSTRAINT: Budget cap is $500 total.",
        required_tokens=("budget",),
        direct_question="What is the budget rule?",
        exact_use_scenario="Decide whether a $450 purchase fits and state the cap.",
        exact_use_required_tokens=("$500",),
    )
    generic = "Budget restrictions remain in force. Be careful with purchases."
    result = ExactUseProbe().probe(canary, generic)
    assert result.direct_pass  # the topic survived
    assert result.exact_use_pass is False  # the value did not
    assert not result.survived
    assert not SimulatedAgent().answer_exact_use(canary, generic).found

    exact = "HARD CONSTRAINT: Budget cap is $500 total."
    assert ExactUseProbe().probe(canary, exact).survived
    assert SimulatedAgent().answer_exact_use(canary, exact).found


def test_seeded_canaries_carry_exact_use_probes():
    canaries = seeded_canaries()
    with_exact = [c for c in canaries if c.exact_use_scenario]
    assert len(with_exact) >= 12
    for c in with_exact:
        assert c.exact_use_required_tokens
