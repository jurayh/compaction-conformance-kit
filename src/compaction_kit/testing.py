"""Helpers for testing compactors inside a test suite.

`check_compactor` runs a compactor through the conformance runner
and returns the report. The `assert_*` helpers turn report verdicts
into test failures with the diagnosis attached, so a failing test
says which canaries died, in which round, and what is missing:

    from compaction_kit.testing import assert_no_flags, check_compactor

    def test_my_compactor():
        report = check_compactor(MyCompactor(), rounds=5, budget_fraction=0.2)
        assert_no_flags(report)

The pytest plugin (`compaction_kit.pytest_plugin`) wraps these in
fixtures; this module itself has no pytest dependency.
"""

from __future__ import annotations

from .canaries import Canary, seeded_canaries
from .compactors import Compactor
from .report import ConformanceReport, budget_check_from_run, build_report
from .runner import run_conformance
from .session import SeededSession, build_seeded_session


def check_compactor(
    compactor: Compactor,
    *,
    session: SeededSession | None = None,
    canaries: list[Canary] | None = None,
    rounds: int = 5,
    budget_fraction: float | None = None,
) -> ConformanceReport:
    """Run one compactor and return its conformance report.

    Defaults to the seeded session and canaries. With
    `budget_fraction`, a budget check at that fraction is attached
    to the report (see `ConformanceReport.budget_checks`).
    """
    session = session if session is not None else build_seeded_session()
    canaries = canaries if canaries is not None else seeded_canaries()
    run = run_conformance(session, compactor, rounds=rounds, canaries=canaries)
    report = build_report(run, canaries=canaries, session=session)
    present = {canary.type.value for canary in canaries}
    report.findings = [f for f in report.findings if f.canary_type in present]
    if budget_fraction is not None:
        budgeted = run_conformance(
            session, compactor, rounds=rounds,
            canaries=canaries, budget_fraction=budget_fraction,
        )
        report.budget_checks.append(budget_check_from_run(budgeted, budget_fraction))
    return report


def _failure_message(report: ConformanceReport, headline: str) -> str:
    lines = [headline]
    for finding in report.findings:
        if finding.verdict == "FLAG":
            lines.append(
                f"- {finding.canary_type}: FLAGGED at round 1 "
                f"({finding.round1_survival:.0%} survival)"
            )
        if finding.has_late_cliff:
            lines.append(
                f"- {finding.canary_type}: late cliff at round {finding.cliff_round}"
            )
    for check in report.budget_checks:
        if not check.compliant:
            over = [
                result.round_num
                for result in check.rounds
                if not result.within_budget
            ]
            lines.append(
                f"- budget {check.budget_fraction:.0%}: over budget in "
                f"round(s) {', '.join(str(r) for r in over)}"
            )
    lost = [d for d in report.diagnoses if d.lost or d.stale_tokens]
    for diagnosis in lost:
        detail = f"- lost canary {diagnosis.canary_id} ({diagnosis.canary_type})"
        if diagnosis.lost_round is not None:
            detail += f" at round {diagnosis.lost_round}"
        if diagnosis.missing_tokens:
            detail += f"; missing: {', '.join(diagnosis.missing_tokens)}"
        if diagnosis.stale_tokens:
            detail += f"; stale still present: {', '.join(diagnosis.stale_tokens)}"
        lines.append(detail)
    return "\n".join(lines)


def assert_no_flags(report: ConformanceReport) -> None:
    """Fail unless the report is clean: no FLAG, no late cliff, budgets met."""
    if report.flagged_types or report.late_cliff_types or not report.budget_compliant:
        raise AssertionError(
            _failure_message(
                report,
                f"compaction conformance failed for {report.compactor_name}:",
            )
        )


def assert_budget_compliant(report: ConformanceReport) -> None:
    """Fail unless every budget check attached to the report passed."""
    if not report.budget_checks:
        raise AssertionError(
            "report has no budget checks: run check_compactor with "
            "budget_fraction=... (or compaction-kit check --budgets)"
        )
    if not report.budget_compliant:
        raise AssertionError(
            _failure_message(
                report,
                f"budget compliance failed for {report.compactor_name}:",
            )
        )


def assert_type_survival(
    report: ConformanceReport,
    canary_type: str,
    *,
    min_round1: float | None = None,
    min_final: float | None = None,
) -> None:
    """Fail unless one canary type meets the given survival floors."""
    finding = next(
        (f for f in report.findings if f.canary_type == canary_type), None
    )
    if finding is None:
        raise AssertionError(
            f"report for {report.compactor_name} has no finding for "
            f"type {canary_type!r}"
        )
    problems = []
    if min_round1 is not None and finding.round1_survival < min_round1:
        problems.append(
            f"round-1 survival {finding.round1_survival:.0%} < {min_round1:.0%}"
        )
    if min_final is not None and finding.final_survival < min_final:
        problems.append(
            f"final survival {finding.final_survival:.0%} < {min_final:.0%}"
        )
    if problems:
        raise AssertionError(
            _failure_message(
                report,
                f"{canary_type} survival too low for {report.compactor_name}: "
                + "; ".join(problems),
            )
        )
