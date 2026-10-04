# Multi-seed corpus test

The seeded session is one hand-built transcript. This test asks whether
the kit's separation holds across many randomized sessions, and what it
misses.

## Method

- 12 generated sessions (`build_random_session(seed)`, seeds 1-12), each
  with 20 canaries (4 per type), randomized values, shuffled planting
  positions, and varied phrasing.
- Every reference compactor ran 5 iterative rounds per session.
- Two canaries per session are updates: a budget cap and a deadline
  whose earlier values are planted first and superseded later. Holding
  the latest value is survival; carrying the stale value matters.
- An altered-value control replaces the current cap with the stale cap
  in the full session text and checks the probe counts it as lost.

## Results

Median per-type survival across the 12 sessions:

| Compactor | Round 1 median | Round 5 median | Cliff rounds |
| --- | --- | --- | --- |
| lossy-truncation | 25-38% by type | 0% on every type | round 1-2 |
| naive-summary | 0-25% by type | 0-25% by type | round 1 |
| checklist-carrying | 100% on every type | 100% on every type | none |

The separation is not an artifact of the seeded session. Checklist
survival was 100% for every type in every seed at every round; lossy
truncation decayed to zero on every type by round 5 in the median
session.

## Position effect

Truncation survival by planting position (round 1, then round 5):

| Position | Round 1 | Round 5 |
| --- | --- | --- |
| early | 0% | 0% |
| middle | 1% | 0% |
| late | 93% | 0% |

Late-planted canaries survive the first truncation because they are in
the tail; repeated rounds still erase them. Position buys one round,
not safety.

## Supersession: the over-preservation problem

Holding the latest value is only half the story. Final-round results
for the two update canaries (12 sessions each):

| Compactor | Latest held | Stale also present | Stale only |
| --- | --- | --- | --- |
| checklist-carrying | 12/12 | 12/12 | 0/12 |
| lossy-truncation | 0/12 | 0/12 | 0/12 |
| naive-summary (deadline) | 2/12 | 2/12 | 0/12 |

The checklist compactor never loses the latest value, but its
marker-based extraction also carries the superseded value alongside it
in all 12 sessions. A context containing both the old and new cap is
ambiguous to act on, even though token survival counts it as held.
Preservation and update resolution are different conformance axes, and
the kit now measures the second one: a stale value carried without the
latest counts as a stale leak, and stale-alongside-latest is reported
rather than hidden inside a survival pass.

The altered-value control passes: replacing the current cap with the
stale cap in the session text makes the probe count the canary as lost.

## Verdict

The metric is stable across sessions for the separation it was built
to make, and the corpus exposed a real limitation of the
structure-preserving reference: it preserves, but it does not resolve
updates. Next compactor work should be measured on both axes.

Raw aggregates: `examples/corpus-results.json`. Generator:
`src/compaction_kit/corpus.py`. Runner: `tools/run_corpus.py`.
