# Generated rotating corpus

The seeded session and the randomized corpus reuse fixed subjects
and one phrasing per canary, so a compactor can be tuned to them.
The generated corpus (`compaction_kit.generated`) rotates everything
a tuner would memorize:

- **Subjects.** Each session samples 2 of 4 subjects per canary type
  from a pool of 20, so most subjects in a fresh session were not in
  the last one. Across seeds 1-12 all 20 subjects appear.
- **Phrasing.** Every subject has three paraphrase templates; an
  update restates its new value in different words than the old one.
- **Values.** Codes, caps, dates, names, and phrases are generated
  per seed and kept distinct across canaries, updates, and
  distractors within a session.
- **Updates.** Three canaries per session are superseded mid-session;
  the ground truth is the latest value, the old value is stale.
- **Distractors.** Four statements about unchosen subjects, same
  shapes and type prefixes as real canaries, planted as plain turns.
  No probe asks for them; they exist so "keep lines that look
  important" is not, by itself, a strategy.

Sessions are deterministic per seed, so a CI job can rotate the seed
on a schedule and still reproduce any failure from the seed alone:

```bash
compaction-kit corpus --generated --seeds 1-12
compaction-kit check my_compactor.py:MyCompactor --generated-seed 42
```

The GitHub Action takes a `generated-seed` input for the same
rotation in check mode.

## Measured results (seeds 1-12, 3 rounds, final survival)

| Compactor | Mean final survival | Min seed | Notes |
| --- | --- | --- | --- |
| checklist-carrying | 100% | 100% | carries stale values too (36/36 updates) |
| semantic-checklist | 94.2% | 80% (seed mean) | latest held in 32/36 updates, fully resolved (no stale carried) in 14/36 |
| lossy-truncation | 0% | 0% | flagged on every type |

## Finding: the semantic resolver has a paraphrase blind spot

The rotating corpus immediately earned its keep. The semantic
resolver lost the budget-cap canary in 5 of 6 sessions where it
appeared, always with the same paraphrase: "Never let total spending
pass $815 without explicit approval." Its spending classifier keys
on words like "cap", "capped", and "budget"; this phrasing has none
of them, so the statement fell out of the governed set entirely and
was dropped rather than carried. The other two cap paraphrases
survive. Branch and base-commit each lost one instance the same way.

That is a genuine limitation of the reference resolver on unseen
phrasing, recorded here rather than tuned around: the generator's
job is to keep producing statements the compactors have not seen.
Widening the classifier is a separate change.

The update numbers carry the same lesson. On its own semantic
corpus the resolver resolves every conflict, because those subjects
are its governed domains. Here most update subjects sit outside
those domains, so both values ride the ordinary checklist path:
latest held in 32 of 36 updates, but fully resolved, with no stale
value carried, in only 14.
