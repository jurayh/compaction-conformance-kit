import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit.compactors import ChecklistCompactor, LossyTruncationCompactor
from compaction_kit.corpus import build_random_session, position_bucket
from compaction_kit.probes import BehaviorProbe
from compaction_kit.runner import run_conformance


def test_random_session_is_deterministic_and_balanced():
    s1, c1 = build_random_session(7)
    s2, c2 = build_random_session(7)
    assert [c.content for c in c1] == [c.content for c in c2]
    assert s1.full_text() == s2.full_text()
    assert len(c1) == 20
    from collections import Counter

    assert set(Counter(c.type for c in c1).values()) == {4}
    for c in c1:
        assert c.id in s1.canary_positions
        assert position_bucket(s1, c.id) in {"early", "middle", "late"}


def test_update_canaries_have_stale_predecessors():
    session, canaries = build_random_session(3)
    text = session.full_text().lower()
    for c in canaries:
        if c.superseded_tokens:
            assert c.required_tokens
            # latest statement is planted; stale tokens exist earlier in text
            for tok in c.superseded_tokens:
                assert tok.lower() in text


def test_altered_value_does_not_count_as_survival():
    session, canaries = build_random_session(5)
    cap = next(c for c in canaries if c.id == "r-constraint-1")
    text = session.full_text()
    assert BehaviorProbe().probe(cap, text).survived
    altered = text.replace(cap.required_tokens[0], cap.superseded_tokens[0])
    assert not BehaviorProbe().probe(cap, altered).survived


def test_corpus_separates_checklist_from_lossy_across_seeds():
    for seed in (1, 2, 3):
        session, canaries = build_random_session(seed)
        good = run_conformance(session, ChecklistCompactor(), rounds=5, canaries=canaries)
        bad = run_conformance(session, LossyTruncationCompactor(), rounds=5, canaries=canaries)
        for rate in good.rounds[-1].survival_by_type.values():
            assert rate == 1.0
        assert sum(bad.rounds[-1].survival_by_type.values()) < sum(
            good.rounds[-1].survival_by_type.values()
        )
