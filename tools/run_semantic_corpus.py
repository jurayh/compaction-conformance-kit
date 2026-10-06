"""Semantic-conflict corpus runs: development and held-out sessions.

For each seed, builds a semantic session, runs every compactor for 5
rounds, and measures: conflict latest-held vs stale-carried, and
distinct near-duplicate pairs both-held. The held-out sessions use new
templates and non-overlapping subjects so resolver performance is not
judged only on the development wording. Writes
examples/semantic-corpus-results.json. No canary values are printed.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit.compactors import (
    ChecklistCompactor,
    LossyTruncationCompactor,
    NaiveSummaryCompactor,
    PinnedRulesCompactor,
    UpdateAwareChecklistCompactor,
)
from compaction_kit.runner import run_conformance
from compaction_kit.semantic import SemanticChecklistCompactor
from compaction_kit.semantic_corpus import (
    build_semantic_heldout_session,
    build_semantic_session,
)

SEEDS = list(range(1, 9))
ROUNDS = 5
COMPACTORS = [
    LossyTruncationCompactor(),
    NaiveSummaryCompactor(),
    PinnedRulesCompactor(),
    ChecklistCompactor(),
    UpdateAwareChecklistCompactor(),
    SemanticChecklistCompactor(),
]


def evaluate(compactor, builder) -> dict:
    conf = defaultdict(lambda: {
        "n": 0, "latest": 0, "stale": 0, "both": 0,
        "stale_only": 0, "resolved": 0,
    })
    pairs = defaultdict(lambda: {"n": 0, "both_held": 0})
    for seed in SEEDS:
        session, canaries, meta = builder(seed)
        run = run_conformance(session, compactor, rounds=ROUNDS, canaries=canaries)
        final = run.rounds[-1]
        text = final.context.text.lower()
        for cid in meta["conflicts"]:
            canary = next(item for item in canaries if item.id == cid)
            latest = all(token.lower() in text for token in canary.required_tokens)
            stale = any(token.lower() in text for token in canary.superseded_tokens)
            entry = conf[cid]
            entry["n"] += 1
            entry["latest"] += int(latest)
            entry["stale"] += int(stale)
            entry["both"] += int(latest and stale)
            entry["stale_only"] += int(stale and not latest)
            entry["resolved"] += int(latest and not stale)
        for first, second in meta["distinct_pairs"]:
            key = f"{first}+{second}"
            pairs[key]["n"] += 1
            pairs[key]["both_held"] += int(
                final.survived.get(first) and final.survived.get(second)
            )
    return {
        "conflicts": {key: dict(value) for key, value in sorted(conf.items())},
        "conflict_totals": {
            "n": sum(value["n"] for value in conf.values()),
            "latest": sum(value["latest"] for value in conf.values()),
            "resolved": sum(value["resolved"] for value in conf.values()),
            "both": sum(value["both"] for value in conf.values()),
            "stale_only": sum(value["stale_only"] for value in conf.values()),
        },
        "distinct_pairs": {
            key: dict(value) for key, value in sorted(pairs.items())
        },
        "distinct_pair_totals": {
            "n": sum(value["n"] for value in pairs.values()),
            "both_held": sum(value["both_held"] for value in pairs.values()),
        },
    }


def print_result(label: str, name: str, result: dict) -> None:
    totals = result["conflict_totals"]
    pairs = result["distinct_pair_totals"]
    print(
        f"== [{label}] {name}: conflicts latest {totals['latest']}/{totals['n']}, "
        f"resolved {totals['resolved']}/{totals['n']}, both {totals['both']}, "
        f"stale_only {totals['stale_only']}; distinct pairs "
        f"{pairs['both_held']}/{pairs['n']}"
    )


def main() -> None:
    payload = {
        "seeds": SEEDS,
        "rounds": ROUNDS,
        "by_compactor": {},
        "heldout_by_compactor": {},
    }
    corpora = [
        ("development", build_semantic_session, "by_compactor"),
        ("heldout", build_semantic_heldout_session, "heldout_by_compactor"),
    ]
    for label, builder, payload_key in corpora:
        for compactor in COMPACTORS:
            result = evaluate(compactor, builder)
            payload[payload_key][compactor.name] = result
            print_result(label, compactor.name, result)

    out = Path(__file__).resolve().parents[1] / "examples" / "semantic-corpus-results.json"
    out.write_text(json.dumps(payload, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
