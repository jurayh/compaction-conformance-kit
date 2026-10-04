import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit.compactors import (
    ChecklistCompactor,
    PinnedRulesCompactor,
    UpdateAwareChecklistCompactor,
)
from compaction_kit.corpus import build_random_session
from compaction_kit.runner import run_conformance
from compaction_kit.session import build_seeded_session


def test_update_aware_resolves_superseded_values():
    for seed in (1, 2, 3):
        session, canaries = build_random_session(seed)
        run = run_conformance(session, UpdateAwareChecklistCompactor(), rounds=5, canaries=canaries)
        final_text = run.rounds[-1].context.text.lower()
        for c in canaries:
            if c.superseded_tokens:
                assert all(t.lower() in final_text for t in c.required_tokens), (seed, c.id)
                assert not any(t.lower() in final_text for t in c.superseded_tokens), (seed, c.id)


def test_update_aware_keeps_full_survival():
    for seed in (1, 2, 3):
        session, canaries = build_random_session(seed)
        run = run_conformance(session, UpdateAwareChecklistCompactor(), rounds=5, canaries=canaries)
        for r in run.rounds:
            for rate in r.survival_by_type.values():
                assert rate == 1.0, (seed, r.round_num, rate)


def test_plain_checklist_carries_stale_values_by_comparison():
    session, canaries = build_random_session(1)
    run = run_conformance(session, ChecklistCompactor(), rounds=5, canaries=canaries)
    final_text = run.rounds[-1].context.text.lower()
    stale_seen = [
        c.id for c in canaries
        if c.superseded_tokens and any(t.lower() in final_text for t in c.superseded_tokens)
    ]
    assert stale_seen, "plain checklist is expected to carry superseded values"


def test_pinned_rules_protect_only_rules_and_constraints():
    session, canaries = build_random_session(2)
    run = run_conformance(session, PinnedRulesCompactor(), rounds=5, canaries=canaries)
    final = run.rounds[-1].survival_by_type
    assert final["safety_rule"] == 1.0
    assert final["hard_constraint"] == 1.0
    assert final["fact"] < 1.0


def test_update_aware_on_seeded_session():
    session = build_seeded_session()
    run = run_conformance(session, UpdateAwareChecklistCompactor(), rounds=5)
    for r in run.rounds:
        for rate in r.survival_by_type.values():
            assert rate == 1.0
