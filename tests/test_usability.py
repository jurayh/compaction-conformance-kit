import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit import (
    build_report,
    build_seeded_session,
    diagnose_run,
    diff_reports,
    init_project,
    load_canaries,
    load_compactor,
    seeded_canaries,
)
from compaction_kit.cli import main as cli_main
from compaction_kit.compactors import ChecklistCompactor, LossyTruncationCompactor
from compaction_kit.runner import run_conformance

USER_MODULE = '''
from compaction_kit import CompactedContext


class TailCompactor:
    name = "user-tail"

    def compact(self, turns, round_num=1, budget_chars=None):
        text = "\\n".join(f"[{t.role}] {t.text}" for t in turns)[-2000:]
        return CompactedContext(text=text, compactor_name=self.name, round_num=round_num)
'''


def _run(session, compactor):
    return run_conformance(session, compactor, rounds=5)


def test_load_compactor_from_file_and_module(tmp_path=None):
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "mine.py"
        path.write_text(USER_MODULE)
        compactor = load_compactor(f"{path}:TailCompactor")
        assert compactor.name == "user-tail"
        module_compactor = load_compactor("compaction_kit.compactors:ChecklistCompactor")
        assert module_compactor.name == "checklist-carrying"
        for bad in ("no-colon", "missing.py:Nope", "compaction_kit.compactors:Nope"):
            try:
                load_compactor(bad)
            except ValueError:
                pass
            else:
                raise AssertionError(f"{bad} must be rejected")


def test_check_command_exit_codes(tmp_path=None):
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "mine.py"
        path.write_text(USER_MODULE)
        with contextlib.redirect_stdout(io.StringIO()):
            rc_bad = cli_main(["check", f"{path}:TailCompactor"])
            rc_good = cli_main(["check", "compaction_kit.compactors:ChecklistCompactor"])
            rc_err = cli_main(["check", "missing.py:Nope"])
        assert rc_bad == 1  # tail-only compaction loses early canaries
        assert rc_good == 0
        assert rc_err == 2


def test_init_scaffold_is_loadable(tmp_path=None):
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        results = init_project(tmp)
        created = {p.name for p, was_created in results if was_created}
        assert {"my_compactor.py", "canaries.json", "compaction.yml"} <= created | {
            p.name for p, _ in results
        }
        canaries = load_canaries(Path(tmp) / "canaries.json")
        assert len(canaries) == 2
        workflow = (Path(tmp) / ".github" / "workflows" / "compaction.yml").read_text()
        assert "jurayh/compaction-conformance-kit@main" in workflow
        # second run without force creates nothing
        assert all(not created for _, created in init_project(tmp))
        # the scaffolded compactor itself runs through the checker
        with contextlib.redirect_stdout(io.StringIO()):
            rc = cli_main(["check", str(Path(tmp) / "my_compactor.py") + ":MyCompactor"])
        assert rc in (0, 1)  # a verdict, not a crash


def test_diff_reports_and_command(tmp_path=None):
    import tempfile

    session = build_seeded_session()
    good = build_report(
        _run(session, ChecklistCompactor()),
        canaries=seeded_canaries(), session=session,
    ).to_dict()
    bad = build_report(
        _run(session, LossyTruncationCompactor()),
        canaries=seeded_canaries(), session=session,
    ).to_dict()
    assert diff_reports(good, bad).has_regressions
    assert not diff_reports(bad, good).has_regressions
    assert not diff_reports(good, good).has_regressions

    with tempfile.TemporaryDirectory() as tmp:
        baseline = Path(tmp) / "baseline.json"
        current = Path(tmp) / "current.json"
        baseline.write_text(json.dumps(good))
        current.write_text(json.dumps(bad))
        with contextlib.redirect_stdout(io.StringIO()):
            assert cli_main(["diff", str(baseline), str(current)]) == 1
            assert cli_main(["diff", str(current), str(baseline)]) == 0
            assert cli_main(["diff", str(baseline), str(Path(tmp) / "nope.json")]) == 2


def test_diagnosis_identifies_losses(tmp_path=None):
    session = build_seeded_session()
    run = _run(session, LossyTruncationCompactor())
    diagnoses = diagnose_run(run, seeded_canaries(), session)
    by_id = {d.canary_id: d for d in diagnoses}
    safety = by_id["safety-001"]  # planted early
    assert safety.lost and safety.lost_round == 1
    assert safety.position == "early"
    assert safety.missing_tokens  # something specific is missing
    good = diagnose_run(_run(session, ChecklistCompactor()), seeded_canaries(), session)
    assert all(not d.lost and not d.stale_tokens for d in good)


def test_report_html_and_json_include_diagnosis():
    session = build_seeded_session()
    report = build_report(
        _run(session, LossyTruncationCompactor()),
        canaries=seeded_canaries(), session=session,
    )
    html = report.to_html()
    assert "<svg" in html and "Diagnosis" in html and "safety-001" in html
    payload = json.loads(report.to_json())
    assert payload["diagnoses"]
    assert any(d["canary_id"] == "safety-001" for d in payload["diagnoses"])
    assert "## Diagnosis" in report.to_markdown()
