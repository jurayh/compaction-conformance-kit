import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit.compactors import ChecklistCompactor, UpdateAwareChecklistCompactor
from compaction_kit.runner import run_conformance
from compaction_kit.semantic_corpus import build_semantic_session


def test_semantic_session_structure():
    s1, c1, m1 = build_semantic_session(4)
    s2, c2, m2 = build_semantic_session(4)
    assert s1.full_text() == s2.full_text()
    assert len(m1["conflicts"]) == 8
    assert len(m1["distinct_pairs"]) == 3
    text = s1.full_text()
    turn_texts = [t.text for t in s1.turns]
    for cid in m1["conflicts"]:
        canary = next(c for c in c1 if c.id == cid)
        assert canary.superseded_tokens
        assert turn_texts.index(m1["initial_statements"][cid]) < s1.canary_positions[cid]


def test_checklist_preserves_distinct_pairs():
    for seed in (1, 2):
        session, canaries, meta = build_semantic_session(seed)
        run = run_conformance(session, ChecklistCompactor(), rounds=5, canaries=canaries)
        final = run.rounds[-1]
        for a, b in meta["distinct_pairs"]:
            assert final.survived[a] and final.survived[b], (seed, a, b)


def test_current_compactors_do_not_resolve_semantic_conflicts():
    # Diagnostic benchmark: marker extraction captures the stale typed
    # statement, while paraphrased updates are not resolved. A future
    # semantic compactor should make this test fail and be replaced.
    session, canaries, meta = build_semantic_session(1)
    for compactor in (ChecklistCompactor(), UpdateAwareChecklistCompactor()):
        run = run_conformance(session, compactor, rounds=5, canaries=canaries)
        text = run.rounds[-1].context.text.lower()
        resolved = 0
        for cid in meta["conflicts"]:
            c = next(x for x in canaries if x.id == cid)
            latest = all(t.lower() in text for t in c.required_tokens)
            stale = any(t.lower() in text for t in c.superseded_tokens)
            resolved += int(latest and not stale)
        assert resolved <= 2, (compactor.name, resolved)
