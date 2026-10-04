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

## 5. Measure your own compaction

Implement one method:

```python
class MyCompactor:
    name = "my-compaction"
    def compact(self, turns, round_num=1):
        ...  # return CompactedContext(text=..., compactor_name=..., round_num=...)
```

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
