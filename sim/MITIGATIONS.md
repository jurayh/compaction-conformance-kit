# Mitigation comparison

Which compaction designs actually preserve what matters, and which
resolve updates instead of carrying stale values? Every compactor below
ran the same 12 randomized sessions (20 canaries each) for 5 iterative
rounds. Two axes: per-type survival, and supersession (the update
canaries' latest value vs the stale one).

## Survival (median across 12 sessions)

| Compactor | Round 1 | Round 5 | Notes |
| --- | --- | --- | --- |
| lossy-truncation | 25-38% | 0% all types | cliff rounds 1-2 |
| naive-summary | 0-25% | 0-25% | flat and low |
| summary-plus-tail | 25-38% | 0% all types | the raw tail does not survive repeated rounds |
| pinned-rules | safety/constraint 100%, rest 0-25% | same | protects exactly what it pins, nothing else |
| checklist-carrying | 100% all types | 100% all types | preserves everything, including stale values |
| update-aware-checklist | 100% all types | 100% all types | preserves and resolves updates |

## Supersession (final round, 12 sessions per update canary)

| Compactor | Latest held | Stale also present |
| --- | --- | --- |
| checklist-carrying | 12/12 | 12/12 |
| pinned-rules (cap) | 12/12 | 12/12 |
| update-aware-checklist | 12/12 | 0/12 |
| lossy / naive / summary+tail | 0-2/12 | 0-2/12 |

## Reading

- **Summary-plus-tail is not a mitigation under repeated compaction.**
  The tail is itself compacted next round, so the hybrid converges to
  the lossy result by round 5.
- **Pinning works, narrowly.** Safety rules and hard constraints held
  at 100% across all seeds and rounds, while facts, goal state, and
  preferences stayed at naive-summary levels. Pinning is a safety
  floor, not a memory strategy. It also carries both old and new caps,
  so pinning alone does not resolve updates.
- **The checklist is the strongest memory, and it over-preserves.**
  It never loses the latest value, but marker extraction carries
  superseded values next to them, leaving the agent an ambiguous
  context.
- **Update-aware checklist passes both axes.** Keying typed items with
  volatile values masked (amounts, dates, hashes) and keeping the
  latest statement per key holds 100% survival while stale presence
  drops to 0/12. That was the kill criterion for this comparison, and
  it passes without giving up survival.

Caveat: update resolution here is keyed on the typed-item text with
values masked. It resolves re-statements of the same item; it does not
detect that two differently worded items conflict. That harder problem
needs semantic keying, and the corpus can measure it when a compactor
attempts it.

Raw aggregates: `examples/mitigations-results.json`. Runner:
`tools/run_mitigations.py`. Implementations:
`src/compaction_kit/compactors.py`.
