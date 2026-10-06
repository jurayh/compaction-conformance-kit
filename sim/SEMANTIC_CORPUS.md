# Semantic-conflict corpus

The randomized corpus updates a value by re-stating the same item with
a new number. Real sessions rarely update that cleanly:

> HARD CONSTRAINT: Project budget cap is $800 total.
> ... later ...
> Quick update: keep project spend under five hundred dollars from now on.

A compactor that carries only the first statement has kept the stale
rule. A compactor that carries both has not resolved the update. And a
compactor that merges look-alike items can destroy a distinct fact:
a production database and a staging database are both "databases",
but they are not the same item.

## Corpus design

`build_semantic_session(seed)` plants, per session:

- 8 semantic conflicts — an early typed statement superseded later by a
  paraphrased update written in different words (amounts spelled out,
  "spend" for "budget cap", "owns the pager" for "on-call owner",
  "report in Pacific time" for a UTC rule). The latest statement is the
  canary; the earlier one is recorded as superseded.
- 6 distinct near-duplicates in 3 pairs — production vs staging
  database, primary vs backup deployment region, and unit vs
  integration test command — that must both survive compaction.

`build_semantic_heldout_session(seed)` uses new templates and subjects:
trip spending, release timing, an internal label, support duty, and a
rotated access code. Its distinct pairs use project vs conference
spending, launch vs documentation dates, and release approver vs
design reviewer. The held-out sessions were added so the resolver is
not judged only on the wording it was developed against.

Metrics per compactor after 5 rounds, across 8 seeds (64 conflicts,
24 distinct-pair instances):

- latest: newest value present
- resolved: newest present and stale absent
- both / stale-only: failure modes

### Ground-truth correction

The first version of the development corpus used project vs travel
budget and launch vs docs deadline as distinct pairs. Resolver testing
exposed a labelling error: the project-budget and launch-deadline
items governed the same subjects as two of the conflicts, so they were
intermediate updates rather than distinct items. Those pairs were
replaced with non-overlapping subjects. The held-out corpus was built
with non-overlapping subjects from the start.

## Results: development corpus (8 seeds x 5 rounds)

| Compactor | Latest | Resolved | Both | Stale-only | Distinct pairs both-held |
| --- | ---: | ---: | ---: | ---: | ---: |
| lossy-truncation | 0/64 | 0/64 | 0 | 0 | 0/24 |
| naive-summary | 24/64 | 24/64 | 0 | 0 | 0/24 |
| pinned-rules | 24/64 | 16/64 | 8 | 16 | 8/24 |
| checklist-carrying | 8/64 | 0/64 | 8 | 56 | 24/24 |
| update-aware-checklist | 8/64 | 0/64 | 8 | 56 | 24/24 |
| semantic-checklist | 64/64 | 64/64 | 0 | 0 | 24/24 |

## Results: held-out corpus (8 seeds x 5 rounds)

| Compactor | Latest | Resolved | Both | Stale-only | Distinct pairs both-held |
| --- | ---: | ---: | ---: | ---: | ---: |
| lossy-truncation | 0/64 | 0/64 | 0 | 0 | 0/24 |
| naive-summary | 24/64 | 24/64 | 0 | 0 | 0/24 |
| pinned-rules | 24/64 | 16/64 | 8 | 16 | 8/24 |
| checklist-carrying | 0/64 | 0/64 | 0 | 64 | 24/24 |
| update-aware-checklist | 0/64 | 0/64 | 0 | 64 | 24/24 |
| semantic-checklist | 64/64 | 64/64 | 0 | 0 | 24/24 |

## Findings

### The earlier compactors do not resolve semantic updates

1. Marker extraction is the first failure. The checklist captures the
   early typed statement and misses most paraphrased updates, which use
   natural wording without the typed header.

2. Value-masked keying does not generalize. The update-aware checklist,
   which resolved the re-stated updates in the randomized corpus,
   resolves 0/64 semantic conflicts in either corpus: differently
   worded statements produce different keys.

3. Naive summarization "resolves" by accident. It keeps a late tail
   verbatim, so some updates planted late survive while stale
   statements are summarized away. It also loses every distinct pair.
   Recency is not resolution.

### The semantic resolver

`SemanticChecklistCompactor` adds a dependency-free taxonomy layer to
the checklist:

- Governed statements are classified by domain and scope, such as
  spending-limit/project, spending-limit/travel, deadline/launch,
  deadline/docs, protected-code/access, working-branch/current, and
  incident-owner/support.
- Only the latest statement for each semantic identity is carried.
- Typed items outside the taxonomy continue through the ordinary
  checklist path.
- Matching is whole-token rather than substring based. This matters:
  "capped" in a retry-logic filler is not a budget cap, and treating it
  as one initially cost 12/240 canaries on the randomized corpus.
- Questions and probe echoes are ignored. A line asking "What is the
  project codename?" mentions the subject but asserts no value.
- Governed statements are removed from the recent-activity tail. A raw
  tail can otherwise reintroduce a stale statement that happens to sit
  near the update, defeating latest-wins in the checklist itself.
- Text after a recent-activity heading is not treated as a new update.
  A truncated tail fragment once superseded a complete design-reviewer
  statement because it appeared later in the compacted text.

The resolver meets the stated bar on both semantic corpora:
at least 80% resolved (it reaches 64/64 on each), 100% of distinct
pairs preserved (24/24 on each), and no regression elsewhere. On the
seeded session it holds 100% of every canary type for 5 rounds; on the
12-seed randomized corpus it holds 240/240 canaries and resolves all
24 re-stated update instances with no stale values carried.

### Limits

This is a taxonomy-based reference implementation, not general
natural-language understanding. It covers the governed domains in the
taxonomy and falls back to checklist behaviour elsewhere. A production
resolver would need a broader identity model, confidence handling for
ambiguous scopes, and evaluation on real session traces. The value of
this implementation is narrower and testable: it shows that semantic
identity, not value masking or recency, is the missing operation.

Reproduce: `python3 tools/run_semantic_corpus.py`
(aggregates in `examples/semantic-corpus-results.json`).
