"""Semantic-conflict corpus run.

For each seed, builds a semantic session, runs every compactor for 5
rounds, and measures: conflict latest-held vs stale-carried, and
distinct near-duplicate pairs both-held. Writes
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
from compaction_kit.semantic_corpus import build_semantic_session

SEEDS = list(range(1, 9))
ROUNDS = 5
COMPACTORS = [
    LossyTruncationCompactor(),
    NaiveSummaryCompactor(),
    PinnedRulesCompactor(),
    ChecklistCompactor(),
    UpdateAwareChecklistCompactor(),
]


def main() -> None:
    payload = {"seeds": SEEDS, "rounds": ROUNDS, "by_compactor": {}}
    for compactor in COMPACTORS:
        conf = defaultdict(lambda: {"n": 0, "latest": 0, "stale": 0, "both": 0, "stale_only": 0, "resolved": 0})
        pairs = defaultdict(lambda: {"n": 0, "both_held": 0})
        for seed in SEEDS:
            session, canaries, meta = build_semantic_session(seed)
            run = run_conformance(session, compactor, rounds=ROUNDS, canaries=canaries)
            final = run.rounds[-1]
            text = final.context.text.lower()
            for cid in meta["conflicts"]:
                c = next(x for x in canaries if x.id == cid)
                latest = all(t.lower() in text for t in c.required_tokens)
                stale = any(t.lower() in text for t in c.superseded_tokens)
                d = conf[cid]
                d["n"] += 1
                d["latest"] += int(latest)
                d["stale"] += int(stale)
                d["both"] += int(latest and stale)
                d["stale_only"] += int(stale and not latest)
                d["resolved"] += int(latest and not stale)
            for a, b in meta["distinct_pairs"]:
                key = f"{a}+{b}"
                pairs[key]["n"] += 1
                pairs[key]["both_held"] += int(final.survived.get(a) and final.survived.get(b))
        payload["by_compactor"][compactor.name] = {
            "conflicts": {k: dict(v) for k, v in sorted(conf.items())},
            "conflict_totals": {
                "n": sum(v["n"] for v in conf.values()),
                "latest": sum(v["latest"] for v in conf.values()),
                "resolved": sum(v["resolved"] for v in conf.values()),
                "both": sum(v["both"] for v in conf.values()),
                "stale_only": sum(v["stale_only"] for v in conf.values()),
            },
            "distinct_pairs": {k: dict(v) for k, v in sorted(pairs.items())},
        }
        t = payload["by_compactor"][compactor.name]["conflict_totals"]
        print(f"== {compactor.name}: conflicts latest {t['latest']}/{t['n']}, resolved {t['resolved']}/{t['n']}, both {t['both']}, stale_only {t['stale_only']}")
        print("   distinct pairs:", payload["by_compactor"][compactor.name]["distinct_pairs"])

    out = Path(__file__).resolve().parents[1] / "examples" / "semantic-corpus-results.json"
    out.write_text(json.dumps(payload, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
