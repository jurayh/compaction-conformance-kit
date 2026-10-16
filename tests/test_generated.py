import io
import json
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit.cli import main
from compaction_kit.compactors import ChecklistCompactor, LossyTruncationCompactor
from compaction_kit.generated import (
    CANARIES_PER_SESSION,
    DISTRACTORS_PER_SESSION,
    SUBJECT_COUNT,
    UPDATES_PER_SESSION,
    build_generated_session,
)
from compaction_kit.report import build_report
from compaction_kit.runner import run_conformance
from compaction_kit.semantic import SemanticChecklistCompactor

_PREFIXES = ("SAFETY RULE:", "HARD CONSTRAINT:", "FACT:", "GOAL STATE:", "USER PREFERENCE:")


def _final_survival(factory, seed, rounds=3):
    session, canaries = build_generated_session(seed)
    run = run_conformance(session, factory(), rounds=rounds, canaries=canaries)
    report = build_report(run)
    return sum(f.final_survival for f in report.findings) / len(report.findings)


def test_generated_session_structure_and_determinism():
    session, canaries = build_generated_session(7)
    again, again_canaries = build_generated_session(7)
    assert session.transcript() == again.transcript()
    assert [c.content for c in canaries] == [c.content for c in again_canaries]

    assert len(canaries) == CANARIES_PER_SESSION == 10
    assert SUBJECT_COUNT == 20
    updates = [c for c in canaries if c.superseded_tokens]
    assert len(updates) == UPDATES_PER_SESSION == 3
    by_type = {}
    for c in canaries:
        by_type[c.type.value] = by_type.get(c.type.value, 0) + 1
    assert by_type == {
        "safety_rule": 2, "hard_constraint": 2, "fact": 2,
        "goal_state": 2, "user_preference": 2,
    }
    tagged = [t for t in session.turns if t.canary_id]
    prefixed = [t for t in session.turns if t.text.startswith(_PREFIXES)]
    # 10 canaries + 3 stale predecessors + 4 distractors carry a prefix
    assert len(tagged) == 10
    assert len(prefixed) == 10 + UPDATES_PER_SESSION + DISTRACTORS_PER_SESSION


def test_generated_rotation_and_ground_truth():
    subjects = set()
    contents = set()
    for seed in range(1, 13):
        session, canaries = build_generated_session(seed)
        subjects.update(c.id for c in canaries)
        contents.update(c.content for c in canaries)
        tokens = [c.required_tokens[0] for c in canaries]
        assert len(set(tokens)) == len(tokens)  # values distinct per session
        for c in canaries:
            assert c.required_tokens[0] in c.content.lower() or \
                c.required_tokens[0] in c.content
            if c.superseded_tokens:
                stale = c.superseded_tokens[0]
                assert stale not in c.required_tokens
                # The stale value is stated in a turn before the canary's
                # own turn; match on token boundaries so short values
                # (e.g. the language "go") do not match inside other
                # words or the "GOAL STATE:" prefix itself.
                boundary = r"(?<![A-Za-z0-9]){}(?![A-Za-z0-9])"
                stale_re = re.compile(boundary.format(re.escape(stale.lower())))
                latest_re = re.compile(
                    boundary.format(re.escape(c.required_tokens[0].lower()))
                )
                before = session.turns[: session.canary_positions[c.id]]
                assert any(stale_re.search(t.text.lower()) for t in before)
                assert not any(latest_re.search(t.text.lower()) for t in before)
    assert len(subjects) == 20  # every subject appears within 12 seeds
    assert len(contents) > 100  # phrasing and values genuinely rotate


def test_generated_corpus_separates_compactors():
    for seed in range(1, 7):
        assert _final_survival(ChecklistCompactor, seed) == 1.0
        assert _final_survival(LossyTruncationCompactor, seed) == 0.0
    # The semantic resolver is strong but not perfect on unseen
    # paraphrases: the spending paraphrase without "cap"/"capped"/
    # "budget" keywords escapes its classifier (see
    # sim/GENERATED_CORPUS.md). Pin the floor, not perfection.
    semantic = [_final_survival(SemanticChecklistCompactor, s) for s in range(1, 13)]
    assert sum(semantic) / len(semantic) >= 0.90


def test_generated_cli_paths():
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert main([
            "corpus", "--generated", "--compactor", "checklist-carrying",
            "--seeds", "1-2", "--rounds", "1",
        ]) == 0
    payload = json.loads(buf.getvalue())
    assert payload["corpus_kind"] == "generated"
    entry = payload["by_compactor"]["checklist-carrying"]
    assert all(v == 1.0 for v in entry["final_median_by_type"].values())

    with redirect_stdout(io.StringIO()):
        assert main([
            "check", "compaction_kit.compactors:ChecklistCompactor",
            "--generated-seed", "3", "--rounds", "2",
        ]) == 0
    with redirect_stdout(io.StringIO()):
        assert main([
            "check", "compaction_kit.compactors:ChecklistCompactor",
            "--generated-seed", "3", "--session", "x.jsonl",
            "--canaries", "y.json",
        ]) == 2
