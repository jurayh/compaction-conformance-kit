import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit.cli import main


def test_cli_demo_exits_zero(capsys=None):
    # manual-runner friendly: capture via redirect in the test body
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["demo", "--compactor", "lossy-truncation", "--rounds", "2"])
    out = buf.getvalue()
    assert rc == 0
    assert "lossy-truncation" in out
    assert "FLAG" in out


def test_cli_report_exit_codes():
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc_good = main(["report", "--compactor", "update-aware-checklist", "--format", "json"])
    assert rc_good == 0
    data = json.loads(buf.getvalue())
    assert data["compactor"] == "update-aware-checklist"

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc_bad = main(["report", "--compactor", "lossy-truncation"])
    assert rc_bad == 1


def test_cli_corpus_json():
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["corpus", "--compactor", "update-aware-checklist", "--seeds", "1-2", "--rounds", "3"])
    assert rc == 0
    data = json.loads(buf.getvalue())
    entry = data["by_compactor"]["update-aware-checklist"]
    assert entry["final_median_by_type"]["safety_rule"] == 1.0


def test_cli_all_subcommand_help_exits_zero():
    import io
    from contextlib import redirect_stdout

    for argv in (
        ["--help"],
        ["demo", "--help"],
        ["report", "--help"],
        ["corpus", "--help"],
        ["benchmark", "--help"],
        ["score", "--help"],
    ):
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                main(argv)
        except SystemExit as exc:
            assert exc.code == 0, argv
        else:
            raise AssertionError(f"{argv} did not exit")
        assert "usage:" in buf.getvalue()


def test_cli_rejects_zero_rounds_and_bad_specs():
    import io
    from contextlib import redirect_stderr, redirect_stdout

    def expect_usage_error(argv):
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                main(argv)
        except SystemExit as exc:
            assert exc.code == 2, argv
        else:
            raise AssertionError(f"{argv} did not fail")

    expect_usage_error(["report", "--compactor", "checklist-carrying", "--rounds", "0"])
    expect_usage_error(["demo", "--rounds", "-1"])
    expect_usage_error(["corpus", "--seeds", "3-1"])
    expect_usage_error(["corpus", "--seeds", ""])
    expect_usage_error(["benchmark", "--budgets", ""])
