# Budget benchmark

Survival without a size limit is gameable. A compactor that carries
nearly everything "preserves" perfectly by barely compacting: on the
seeded session, the plain checklist's output grows past 30% of the
original transcript from round 2 onward. A benchmark for compaction
algorithms therefore has to ask the question at a fixed budget:

> At 10%, 20%, or 30% of the original context, what survives, what
> updates correctly, and what stale information leaks?

## Protocol

- Budgets are character caps, expressed as a fraction of the original
  transcript. Characters are exact, deterministic, and
  tokenizer-independent. (A token budget would tie the benchmark to
  one model's tokenizer.)
- The cap is fixed across rounds. A 20% budget means every round's
  output fits in 20% of the original transcript, not 20% of the
  previous round's output.
- A compactor declares budget support by accepting the optional
  `budget_chars` keyword in `compact(turns, round_num, budget_chars)`.
  The original two-argument protocol remains valid: older compactors
  are called unchanged, measured, and marked non-compliant when their
  output exceeds the cap. The benchmark never silently truncates a
  compactor's output to make it fit.
- Reference compactors fit budgets with disclosed policies. Checklist
  variants drop the recent-activity tail first, then select whole
  items in type-priority order (safety rules, hard constraints,
  facts, goal state, user preferences); items are never cut in half.
  Pinned rules give the budget to pinned items first. Summarizers
  shrink their tail/summary components.
- Ranking inside a budget group is lexicographic: budget compliance,
  then overall preservation on the randomized corpus, then semantic
  resolution, then distinct-pair preservation, then smaller output.
  Preservation ranks before resolution so a compactor that loses
  almost everything cannot rank highly for resolving a few updates by
  recency alone. All component metrics are reported, so the ranking
  can be re-derived under a different order.

Suites: the randomized corpus plus the development and held-out
semantic corpora, 8 seeds each, 5 rounds per run. Aggregates are in
`examples/budget-benchmark-results.json`.

Reproduce: `python3 tools/run_budget_benchmark.py`, or
`compaction-kit benchmark --budgets 10%,20%,30%`.

## Results (8 seeds x 5 rounds)

### Budget 10%

| Rank | Compactor | Survival | Semantic resolved | Stale present | Distinct pairs |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | semantic-checklist | 40.0% | 56.2% | 0/128 | 100.0% |
| 2 | update-aware-checklist | 40.0% | 0.0% | 96/128 | 50.0% |
| 3 | pinned-rules | 40.0% | 0.0% | 48/128 | 33.3% |
| 4 | checklist-carrying | 35.0% | 0.0% | 96/128 | 50.0% |
| 5 | lossy-truncation | 0.0% | 0.0% | 0/128 | 0.0% |
| 6 | summary-plus-tail | 0.0% | 0.0% | 0/128 | 0.0% |
| 7 | naive-summary | 0.0% | 0.0% | 0/128 | 0.0% |

### Budget 20%

| Rank | Compactor | Survival | Semantic resolved | Stale present | Distinct pairs |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | semantic-checklist | 85.0% | 100.0% | 0/128 | 100.0% |
| 2 | update-aware-checklist | 85.0% | 0.0% | 128/128 | 100.0% |
| 3 | checklist-carrying | 60.0% | 0.0% | 128/128 | 100.0% |
| 4 | pinned-rules | 40.0% | 0.0% | 48/128 | 33.3% |
| 5 | naive-summary | 10.0% | 25.0% | 0/128 | 0.0% |
| 6 | summary-plus-tail | 5.0% | 12.5% | 0/128 | 0.0% |
| 7 | lossy-truncation | 0.0% | 0.0% | 0/128 | 0.0% |

### Budget 30%

| Rank | Compactor | Survival | Semantic resolved | Stale present | Distinct pairs |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | semantic-checklist | 100.0% | 100.0% | 0/128 | 100.0% |
| 2 | update-aware-checklist | 100.0% | 0.0% | 128/128 | 100.0% |
| 3 | checklist-carrying | 100.0% | 0.0% | 128/128 | 100.0% |
| 4 | pinned-rules | 46.9% | 25.0% | 48/128 | 33.3% |
| 5 | naive-summary | 15.0% | 37.5% | 0/128 | 0.0% |
| 6 | summary-plus-tail | 8.1% | 25.0% | 0/128 | 0.0% |
| 7 | lossy-truncation | 0.0% | 0.0% | 0/128 | 0.0% |

All seven reference compactors are budget-compliant at all three
budgets; the differences above are preservation differences, not
compliance differences.

## Findings

1. **The semantic checklist leads at every budget.** At 20% it
   already reaches the result the other compactors only approach at
   30%: 85% survival, every semantic conflict resolved, no stale
   value present, every distinct pair preserved. At 30% it is at
   100% on all four measures.

2. **Budgets expose the cost of over-preservation.** Without a cap,
   the plain checklist and the update-aware checklist both hold 100%
   on the randomized corpus. At 20%, the plain checklist falls to 60%
   while the update-aware variant holds 85%: the stale duplicates the
   plain checklist carries consume budget that could have held live
   items. Over-preservation is free only when size is free.

3. **Preservation and resolution separate cleanly.** The
   update-aware checklist matches the semantic resolver's survival at
   10% and 20% and reaches 100% at 30%, but it carries a stale value
   in all 128 semantic conflicts at 20% and 30%. It resolves updates
   only when they are re-stated in the same words.

4. **At 10%, the ceiling is structural.** No compactor exceeds 40%
   survival. The semantic resolver still resolves 56.2% of conflicts
   with zero stale values present: when the budget forces a choice,
   it drops whole items rather than carrying stale ones.

5. **Recency is not a strategy.** The naive summarizer resolves
   25–37.5% of semantic conflicts at 20–30% budgets, by keeping late
   text verbatim, while holding only 10–15% overall survival and no
   distinct pairs. The ranking order keeps it below every
   structure-preserving compactor.

## Limits

- Character budgets are a proxy. Real deployments budget tokens, and
  a character cap is not a token guarantee for any specific model.
- The corpora are synthetic. The benchmark measures the compaction
  operation under controlled ground truth; real-trace evaluation is
  the next validation layer.
- The leaderboard ranks the kit's reference compactors. External
  compactors join through the same `budget_chars` protocol; a
  compactor that does not accept a budget can be measured but cannot
  be compliant.
