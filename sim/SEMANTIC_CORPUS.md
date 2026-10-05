# Semantic-conflict corpus

The randomized corpus updates a value by re-stating the same item with
a new number. Real sessions rarely update that cleanly:

> HARD CONSTRAINT: Project budget cap is $800 total.
> ... later ...
> Quick update: keep project spend under five hundred dollars from now on.

A compactor that carries only the first statement has kept the stale
rule. A compactor that carries both has not resolved the update. And a
compactor that merges look-alike items can destroy a distinct fact:
project budget and travel budget are both "budget caps", but they are
not the same item.

## Corpus design

`build_semantic_session(seed)` plants, per session:

- 8 semantic conflicts — an early typed statement superseded later by a
  paraphrased update written in different words (amounts spelled out,
  "spend" for "budget cap", "owns the pager" for "on-call owner",
  "report in Pacific time" for a UTC rule). The latest statement is the
  canary; the earlier one is recorded as superseded.
- 6 distinct near-duplicates in 3 pairs — project vs travel budget,
  launch vs docs deadline, on-call owner vs design reviewer — that must
  both survive compaction.

Metrics per compactor after 5 rounds, across 8 seeds (64 conflicts,
24 distinct-pair instances):

- latest: newest value present
- resolved: newest present and stale absent
- both / stale-only: failure modes

## Results (8 seeds x 5 rounds)

| Compactor | Latest | Resolved | Both | Stale-only | Distinct pairs both-held |
| --- | ---: | ---: | ---: | ---: | ---: |
| lossy-truncation | 0/64 | 0/64 | 0 | 0 | 0/24 |
| naive-summary | 24/64 | 24/64 | 0 | 0 | 0/24 |
| pinned-rules | 24/64 | 16/64 | 8 | 16 | 8/24 |
| checklist-carrying | 16/64 | 0/64 | 16 | 48 | 24/24 |
| update-aware-checklist | 16/64 | 0/64 | 16 | 40 | 24/24 |

## Findings

No current compactor resolves semantic conflicts.

1. Marker extraction is the first failure. The checklist captures the
   early typed statement and misses most paraphrased updates, which use
   natural wording without the typed header. It therefore ends with the
   stale statement alone in 48/64 conflicts, even though it preserves
   every distinct pair perfectly.

2. Value-masked keying does not generalize. The update-aware checklist,
   which resolved 12/12 re-stated updates in the randomized corpus,
   resolves 0/64 here: differently worded statements produce different
   keys, so nothing is recognized as the same item.

3. Naive summarization "resolves" by accident. It keeps a late tail
   verbatim, so updates planted late survive while stale statements are
   summarized away — 24/64 resolved, but it also loses every distinct
   pair. Recency is not resolution.

4. Distinctness is currently safe only under verbatim preservation.
   Checklist-style compaction holds all 24 distinct pairs; anything
   that summarizes or keys aggressively risks merging distinct facts.

The corpus now defines the next real problem for the kit: semantic
update resolution — recognizing that two differently worded statements
govern the same item, latest wins — without collapsing distinct items
that share vocabulary. `tests/test_semantic_corpus.py` encodes the
current failure as a diagnostic benchmark; a semantic compactor that
resolves these conflicts should make that test fail and replace it.

Reproduce: `python3 tools/run_semantic_corpus.py`
(aggregates in `examples/semantic-corpus-results.json`).
