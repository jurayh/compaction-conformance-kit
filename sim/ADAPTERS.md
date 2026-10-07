# External adapters

Until now, every compactor on the leaderboard was written for this
kit. That is the standard objection to a benchmark: of course your
own reference implementations behave well under your own measure.

Two adapters close that hole. Neither knows anything about canaries,
checklists, or the kit's types.

## Progressive summary (LangChain-style)

`ProgressiveSummaryCompactor` implements the summary-buffer pattern
popularized by LangChain's ConversationSummaryBufferMemory:

- a running summary of older turns;
- a verbatim buffer of the most recent turns;
- when the buffer overflows, the oldest turns are folded into the
  summary and dropped from the buffer.

The pattern is re-run on its own output each round, so the summary is
progressively re-summarized, the way the real pattern degrades. The
LLM gist call is a pluggable `summarize_fn`; the default is a
deterministic stand-in that keeps the head of each folded turn, so
the adapter runs with no API key and no model spend. Pass a real
model callable and the same adapter measures that model.

It accepts `budget_chars`, so it entered the budget benchmark with
no special-casing. Result (8 seeds x 5 rounds): budget-compliant at
10/20/30%, randomized survival 0% / 5% / 10%, semantic resolution
0% / 12.5% / 25% (recency, not recognition), distinct pairs 0%.
It ranks with the other unstructured summarizers, below every
structure-preserving compactor. That is the neutrality evidence in
both directions: an external pattern can join the leaderboard, and
joining does not flatter it.

## Score output you produced elsewhere

The stronger form of neutrality: the kit does not need to run your
compactor at all.

```bash
# 1. Run your product's /compact on a session; save the output.
# 2. Score the saved output against known canaries:
compaction-kit score --compacted output.txt --name my-product
echo $?   # 0 = clean, 1 = any type flagged
```

- Default ground truth is the seeded session's canaries; run your
  compaction on the seeded transcript, save the result, score it.
- `--canaries canaries.json` scores against your own canary
  definitions (id, type, content, required tokens) for your own
  transcripts.
- `load_transcript(path)` reads external transcripts (JSONL, JSON,
  or `[role] text` plain text) when you need them as kit sessions.
- `PrecomputedCompactor(text)` replays a saved output through the
  conformance runner unchanged, so one real output gets the full
  per-type report, and exceeds-budget outputs are reported as
  non-compliant rather than silently trimmed.

## Limits

- The default gist is not an LLM. With a real summarizer the
  progressive adapter's numbers will move; the point of the default
  is a reproducible, dependency-free baseline for the pattern.
- At extremely small budgets (roughly under 100 characters) the
  summary-plus-buffer structure itself no longer fits, so the
  adapter degrades to a header fragment. The benchmark budgets
  (10% and up) are far above that floor.
- Scoring external output requires ground truth. The kit supplies
  it for its own sessions and corpora; for production transcripts,
  you supply canaries for the facts and rules you care about.
