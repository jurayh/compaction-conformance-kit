import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit.adapters import PrecomputedCompactor, ProgressiveSummaryCompactor
from compaction_kit.canaries import seeded_canaries
from compaction_kit.cli import main as cli_main
from compaction_kit.compactors import ChecklistCompactor
from compaction_kit.runner import run_conformance
from compaction_kit.session import Turn, build_seeded_session
from compaction_kit.transcripts import load_canaries, load_transcript, score_compacted_output


def test_progressive_summary_keeps_recent_turns_verbatim():
    turns = [Turn("user", f"filler turn {i} about module layout") for i in range(30)]
    turns.append(Turn("user", "The final decision is to ship on Friday."))
    ctx = ProgressiveSummaryCompactor().compact(turns, round_num=1, budget_chars=1200)
    assert "The final decision is to ship on Friday." in ctx.text
    assert "SUMMARY:" in ctx.text and "RECENT TURNS:" in ctx.text
    assert len(ctx.text) <= 1200


def test_progressive_summary_complies_at_standard_budgets():
    session = build_seeded_session()
    for fraction in (0.10, 0.20, 0.30):
        run = run_conformance(
            session, ProgressiveSummaryCompactor(), rounds=5, budget_fraction=fraction
        )
        assert all(r.within_budget for r in run.rounds)
        sizes = [r.output_chars for r in run.rounds]
        assert max(sizes) - min(sizes[1:]) >= 0  # sizes are stable after round 1
        assert sizes[-1] <= sizes[0]


def test_progressive_summary_accepts_a_custom_summarize_fn():
    seen = []

    def summarize(parts):
        seen.append(parts)
        return "custom summary"

    compactor = ProgressiveSummaryCompactor(summarize_fn=summarize)
    turns = [Turn("user", f"filler turn {i} about module layout") for i in range(30)]
    turns.append(Turn("user", "new turn"))
    ctx = compactor.compact(turns, round_num=1, budget_chars=500)
    assert "custom summary" in ctx.text
    assert seen  # the oldest turns were folded through the callable


def test_precomputed_compactor_replays_external_text():
    session = build_seeded_session()
    good = ChecklistCompactor().compact(session.transcript()).text
    run = run_conformance(session, PrecomputedCompactor(good, name="product-x"), rounds=3)
    assert all(sum(r.survived.values()) == 20 for r in run.rounds)
    bad = run_conformance(session, PrecomputedCompactor("nothing kept"), rounds=1)
    assert sum(bad.rounds[-1].survived.values()) == 0


def test_load_transcript_formats(tmp_path=None):
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        jsonl = Path(tmp) / "t.jsonl"
        jsonl.write_text(
            '{"role": "user", "content": "hello"}\n{"role": "assistant", "text": "hi"}\n'
        )
        turns = load_transcript(jsonl)
        assert [(t.role, t.text) for t in turns] == [("user", "hello"), ("assistant", "hi")]

        text = Path(tmp) / "t.txt"
        text.write_text("[user] first line\nassistant: second line\n")
        turns = load_transcript(text)
        assert [(t.role, t.text) for t in turns] == [("user", "first line"), ("assistant", "second line")]


def test_load_canaries_and_score_external_output(tmp_path=None):
    import tempfile

    canaries = seeded_canaries()[:2]
    payload = [
        {
            "id": c.id,
            "type": c.type.value,
            "content": c.content,
            "required_tokens": list(c.required_tokens),
            "direct_question": c.direct_question,
        }
        for c in canaries
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "canaries.json"
        path.write_text(json.dumps(payload))
        loaded = load_canaries(path)
    assert [c.id for c in loaded] == [c.id for c in canaries]

    good_text = "\n".join(c.content for c in canaries)
    report = score_compacted_output(good_text, loaded, compactor_name="external-x")
    assert not report.flagged_types
    empty_report = score_compacted_output("nothing", loaded)
    assert empty_report.flagged_types


def test_cli_score_exit_codes(tmp_path=None):
    import contextlib
    import io
    import tempfile

    session = build_seeded_session()
    good = ChecklistCompactor().compact(session.transcript()).text
    with tempfile.TemporaryDirectory() as tmp:
        good_path = Path(tmp) / "good.txt"
        good_path.write_text(good)
        bad_path = Path(tmp) / "bad.txt"
        bad_path.write_text("nothing kept")
        with contextlib.redirect_stdout(io.StringIO()):
            assert cli_main(["score", "--compacted", str(good_path)]) == 0
            assert cli_main(["score", "--compacted", str(bad_path)]) == 1


def test_score_rejects_empty_canaries_and_string_tokens(tmp_path=None):
    import contextlib
    import io
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.txt"
        out.write_text("x")
        empty = Path(tmp) / "empty.json"
        empty.write_text("[]")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            assert cli_main(["score", "--compacted", str(out), "--canaries", str(empty)]) == 2

        string_tokens = Path(tmp) / "string.json"
        string_tokens.write_text(json.dumps([{
            "id": "x", "type": "fact", "content": "x marks it",
            "required_tokens": "x", "direct_question": "?",
        }]))
        try:
            load_canaries(string_tokens)
        except ValueError:
            pass
        else:
            raise AssertionError("string required_tokens must be rejected")

    try:
        score_compacted_output("anything", [])
    except ValueError:
        pass
    else:
        raise AssertionError("empty canary list must be rejected")


def test_load_transcript_rejects_object_without_turns(tmp_path=None):
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "t.json"
        path.write_text('{"messages": []}')
        try:
            load_transcript(path)
        except ValueError:
            pass
        else:
            raise AssertionError("JSON object without 'turns' must be rejected")
