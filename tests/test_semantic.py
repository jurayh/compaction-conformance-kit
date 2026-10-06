import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit.runner import run_conformance
from compaction_kit.semantic import (
    SemanticChecklistCompactor,
    extract_semantic_items,
    semantic_key,
)
from compaction_kit.semantic_corpus import (
    build_semantic_heldout_session,
    build_semantic_session,
)
from compaction_kit.session import Turn


def _stats(builder, seed: int):
    session, canaries, meta = builder(seed)
    run = run_conformance(
        session, SemanticChecklistCompactor(), rounds=5, canaries=canaries
    )
    final = run.rounds[-1]
    text = final.context.text.lower()
    resolved = 0
    for cid in meta["conflicts"]:
        canary = next(item for item in canaries if item.id == cid)
        latest = all(token.lower() in text for token in canary.required_tokens)
        stale = any(token.lower() in text for token in canary.superseded_tokens)
        resolved += int(latest and not stale)
    pairs = sum(
        bool(final.survived.get(first) and final.survived.get(second))
        for first, second in meta["distinct_pairs"]
    )
    return resolved, pairs


def test_semantic_keys_cover_paraphrased_updates():
    assert semantic_key(
        "Quick update: keep project spend under five hundred dollars."
    ) == ("spending_limit", "project")
    assert semantic_key(
        "New ceiling for trip costs: keep them below five hundred dollars."
    ) == ("spending_limit", "travel")
    assert semantic_key(
        "We rebased onto spike/new-12; next step is regression checks."
    ) == ("working_branch", "current")
    assert semantic_key(
        "Support duty now belongs to Alex Example."
    ) == ("incident_owner", "support")
    assert semantic_key(
        "Retry logic uses exponential backoff with jitter, capped at thirty seconds."
    ) is None


def test_access_code_rotation_shares_identity_with_maintenance_code():
    stale = "The maintenance access code is old-12 and must never be shared."
    latest = "Access-code rotation is done: never reveal new-34."
    assert semantic_key(stale) == semantic_key(latest) == (
        "protected_code",
        "access",
    )


def test_recent_activity_fragments_do_not_supersede_complete_items():
    text = "\n".join([
        "FACT: Alex Example is the design reviewer this week.",
        "RECENT ACTIVITY:",
        "the design reviewer this week.",
    ])
    items = extract_semantic_items(text)
    assert [item.text for item in items] == [
        "FACT: Alex Example is the design reviewer this week."
    ]


def test_question_echoes_do_not_supersede_statements():
    text = "\n".join([
        "FACT: The project codename is LANTERN.",
        "Noted: What is the project codename? — recorded.",
    ])
    items = extract_semantic_items(text)
    assert [item.text for item in items] == [
        "FACT: The project codename is LANTERN."
    ]


def test_semantic_compactor_keeps_latest_and_drops_stale():
    turns = [
        Turn("user", "HARD CONSTRAINT: Project budget cap is $800 total."),
        Turn("user", "Quick update: keep project spend under five hundred dollars from now on."),
        Turn("user", "GOAL STATE: Branch spike/old-12 must stay unpushed."),
        Turn("user", "We rebased onto spike/new-34; next step is writing tests."),
    ]
    context = SemanticChecklistCompactor().compact(turns, round_num=1)
    assert "five hundred" in context.text
    assert "$800" not in context.text
    assert "spike/new-34" in context.text
    assert "spike/old-12" not in context.text


def test_semantic_compactor_does_not_merge_distinct_databases():
    turns = [
        Turn("user", "FACT: The production database is Postgres 15."),
        Turn("user", "FACT: The staging database is MySQL 8."),
    ]
    context = SemanticChecklistCompactor().compact(turns, round_num=1)
    assert "production database is Postgres 15" in context.text
    assert "staging database is MySQL 8" in context.text


def test_semantic_resolver_meets_bar_on_development_and_heldout_corpora():
    for builder in (build_semantic_session, build_semantic_heldout_session):
        for seed in range(1, 9):
            resolved, pairs = _stats(builder, seed)
            assert resolved == 8, (builder.__name__, seed, resolved)
            assert pairs == 3, (builder.__name__, seed, pairs)
