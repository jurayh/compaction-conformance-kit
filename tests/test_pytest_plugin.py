import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit.compactors import ChecklistCompactor, LossyTruncationCompactor
from compaction_kit.semantic import SemanticChecklistCompactor
from compaction_kit.testing import (
    assert_budget_compliant,
    assert_no_flags,
    assert_type_survival,
    check_compactor,
)

ROOT = Path(__file__).resolve().parents[1]


class IgnoreBudgetCompactor:
    name = "ignore-budget"

    def compact(self, turns, round_num=1):
        return SemanticChecklistCompactor().compact(turns, round_num=round_num)


def _expect_assertion(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except AssertionError as exc:
        return str(exc)
    raise AssertionError(f"{fn.__name__} should have raised")


def test_check_compactor_and_assert_no_flags():
    good = check_compactor(ChecklistCompactor(), rounds=3)
    assert_no_flags(good)  # must not raise
    assert {f.canary_type for f in good.findings} == {
        "safety_rule", "hard_constraint", "fact", "goal_state", "user_preference",
    }

    bad = check_compactor(LossyTruncationCompactor(), rounds=3)
    message = _expect_assertion(assert_no_flags, bad)
    assert "FLAGGED" in message
    assert "safety-001" in message  # the diagnosis is in the failure


def test_assert_budget_compliant():
    report = check_compactor(ChecklistCompactor(), rounds=2, budget_fraction=0.20)
    assert report.budget_checks and report.budget_checks[0].compliant
    assert_budget_compliant(report)  # must not raise

    over = check_compactor(IgnoreBudgetCompactor(), rounds=2, budget_fraction=0.10)
    message = _expect_assertion(assert_budget_compliant, over)
    assert "over budget" in message

    no_budget = check_compactor(ChecklistCompactor(), rounds=1)
    message = _expect_assertion(assert_budget_compliant, no_budget)
    assert "no budget checks" in message


def test_assert_type_survival():
    good = check_compactor(ChecklistCompactor(), rounds=2)
    assert_type_survival(good, "safety_rule", min_round1=0.9, min_final=0.9)

    bad = check_compactor(LossyTruncationCompactor(), rounds=2)
    message = _expect_assertion(
        assert_type_survival, bad, "safety_rule", min_round1=0.9
    )
    assert "safety_rule" in message
    message = _expect_assertion(
        assert_type_survival, good, "nonexistent_type", min_round1=0.5
    )
    assert "no finding" in message


def test_pytest_plugin_entry_point_declared():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    entry_points = data["project"]["entry-points"]["pytest11"]
    assert entry_points["compaction_kit"] == "compaction_kit.pytest_plugin"
    if importlib.util.find_spec("pytest") is not None:
        import compaction_kit.pytest_plugin as plugin

        assert hasattr(plugin, "compaction_report")
        assert hasattr(plugin, "compactor")


_INNER_CONFTEST = """
import pytest
from {module} import {cls}


@pytest.fixture
def compactor():
    return {cls}()
"""

_INNER_TEST = """
import pytest
from compaction_kit.testing import assert_no_flags, assert_type_survival


@pytest.mark.compaction(rounds=3, budget_fraction=0.30)
def test_compaction_gate(compaction_report):
    assert_no_flags(compaction_report)
    assert_type_survival(compaction_report, "safety_rule", min_round1=0.9)


def test_seeded_fixtures(seeded_session, seeded_canaries):
    assert len(seeded_canaries) == 20
    assert seeded_session.transcript()
"""


def test_pytest_plugin_end_to_end(tmp_path=None):
    if importlib.util.find_spec("pytest") is None:
        return  # the sandbox has no pytest; CI runs this for real
    src = str(ROOT / "src")
    env = dict(os.environ)
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    cases = [
        ("compaction_kit.compactors", "ChecklistCompactor", 0),
        ("compaction_kit.compactors", "LossyTruncationCompactor", 1),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        for module, cls, expected_rc in cases:
            project = Path(tmp) / cls
            project.mkdir()
            (project / "conftest.py").write_text(
                _INNER_CONFTEST.format(module=module, cls=cls)
            )
            (project / "test_gate.py").write_text(_INNER_TEST)
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                cwd=project, env=env, capture_output=True, text=True,
            )
            assert result.returncode == expected_rc, (
                f"{cls}: rc={result.returncode}\n{result.stdout}\n{result.stderr}"
            )
            if expected_rc == 1:
                assert "FLAGGED" in result.stdout or "FLAGGED" in result.stderr
