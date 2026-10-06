# Quickstart

Five minutes from install to a conformance report for your own
compaction.

## 1. Install

```bash
pip install compaction-conformance-kit
```

## 2. See the failure mode (30 seconds)

```bash
compaction-kit demo
```

One seeded session (20 planted canaries) runs through the built-in
compactors for five rounds each. Truncation loses safety rules in
round 1; the structured compactors do not. That difference is the
whole point of the kit.

## 3. Gate your compaction in CI

```bash
compaction-kit report --compactor update-aware-checklist
echo $?   # 0 = clean, 1 = flagged or late cliff
```

`report` exits 1 when any canary type is flagged at round 1 or falls
off a cliff in a later round, so a compaction change that starts
forgetting safety rules fails the build.

## 4. Check it is not one lucky session

```bash
compaction-kit corpus --seeds 1-12
```

Twelve randomized sessions (fresh values, shuffled positions), JSON
medians out. If a compactor only survives the seeded session, this is
where it shows.

## 5. Compare at a fixed budget

```bash
compaction-kit benchmark --budgets 10%,20%,30%
```

Survival without a size limit is gameable, so the benchmark caps
every compactor's output at a fixed fraction of the original
transcript and ranks what survives at that size.

## 6. Measure your own compaction

Implement one method:

```python
class MyCompactor:
    name = "my-compaction"
    def compact(self, turns, round_num=1, budget_chars=None):
        ...  # return CompactedContext(text=..., compactor_name=..., round_num=...)
```

Accepting the optional `budget_chars` keyword makes your compactor
eligible for the budget benchmark: when it is passed, that round's
output must fit within it. Older two-argument implementations still
work with `demo`, `report`, and `corpus`.

## 7. Or score output you already produced

```bash
compaction-kit score --compacted output.txt --name my-product
```

Run your product's `/compact` on the seeded transcript, save the
output, and score the file. Exit 0 means no canary type is flagged.
For your own transcripts, pass `--canaries canaries.json` with your
own canary definitions.

Runnable version: [../examples/measure_your_compactor.py](../examples/measure_your_compactor.py).
Swap the toy summarizer for your LLM call or your framework's compact
function; the probes, rounds, and report stay the same.

## Reading a report

- **Round 1 / verdict** — FLAG below 50% survival, WARN 50-90%, SILENT
  above 90%.
- **Cliff round** — first round a type falls below 50%. A compactor can
  be SILENT at round 1 and still cliff at round 3; the late-cliff line
  names it.
- **Final** — survival after the last round.
- Survival is per type, never one aggregate. Keeping every fact while
  losing every safety rule is not a passing grade.
