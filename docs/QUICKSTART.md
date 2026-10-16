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

Report and benchmark JSON carry `schema_version` (currently 1),
`kit_version`, and `rounds`, so saved artifacts say which format
they use and which kit produced them. The compatibility policy:
within a schema version, fields are only added, never renamed,
removed, or re-typed, and consumers should ignore fields they do
not know. A breaking change bumps `schema_version`. `diff` reads
only `findings`, so it accepts reports from any kit release,
versioned or not.

## 4. Check it is not one lucky session

```bash
compaction-kit corpus --seeds 1-12
```

Twelve randomized sessions (fresh values, shuffled positions), JSON
medians out. If a compactor only survives the seeded session, this is
where it shows.

For a corpus a compactor cannot be tuned to at all, add
`--generated`: sessions built from a rotating pool of 20 subjects
with three paraphrases each, fresh values, mid-session updates, and
distractor statements that look like canaries but are not graded.
`check` can grade a single generated session with
`--generated-seed N`, which is the rotation to use in CI: change the
seed on a schedule and failures still reproduce from the seed alone.

## 5. Compare at a fixed budget

```bash
compaction-kit benchmark --budgets 10%,20%,30%
```

Survival without a size limit is gameable, so the benchmark caps
every compactor's output at a fixed fraction of the original
transcript and ranks what survives at that size. Your own compactor
joins the leaderboard with
`compaction-kit benchmark --spec my_compactor.py:MyCompactor`.

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

## 8. Or check the class directly

```bash
compaction-kit init
compaction-kit check my_compactor.py:MyCompactor --budgets 10%,20%
```

`init` writes a starter compactor, an example `canaries.json` and
`session.jsonl`, and a CI workflow. `check` loads your class
(`module:Class` or `file.py:Class`), runs the seeded suite, and
verifies any budgets you pass. A budget overrun in any round exits
1, and budget results are carried inside the selected report
format: Markdown gets a budget section, JSON gets a `budget_checks`
array, and HTML gets a budget table.

Then measure against your own data. Replace `session.jsonl` with
your transcript (JSONL, JSON, or plain text) and `canaries.json`
with the rules and facts that session must preserve:

```bash
compaction-kit check my_compactor.py:MyCompactor \
  --session session.jsonl --canaries canaries.json
```

The two flags are a pair: a transcript without its ground truth
would measure against the wrong canaries, so giving only one is a
usage error. The report grades only the canary types your file
defines, and diagnosis locates each canary in your transcript
(early, middle, late). The GitHub Action accepts the same inputs
(`spec`, `session`, `canaries`, `budgets`), and the scaffolded
workflow is already wired to the scaffolded files. Reports end
with a diagnosis section naming each lost
canary, the round it died, and the tokens missing from the final
context; `--format html` gives a self-contained report with the
survival chart.

## 9. Gate changes with diff

Save a baseline report (`report --format json > baseline.json`),
then after a change:

```bash
compaction-kit diff baseline.json current.json
```

Exit 1 means a regression: a type newly flagged, a new or earlier
cliff, or a survival drop of 25 points or more. The repo's GitHub
Action (`action.yml`) runs the same gate in CI.

## 10. Or gate it from pytest

Installing the kit registers a pytest plugin. Define your compactor
once, in `conftest.py`:

```python
import pytest
from my_compactor import MyCompactor

@pytest.fixture
def compactor():
    return MyCompactor()
```

Then the gate is a test:

```python
import pytest
from compaction_kit.testing import assert_no_flags

@pytest.mark.compaction(rounds=5, budget_fraction=0.20)
def test_compaction_gate(compaction_report):
    assert_no_flags(compaction_report)
```

`compaction_report` runs your `compactor` fixture through the
seeded suite; the marker tunes rounds and adds a budget check.
Failures name the flagged types, the lost canaries, and the missing
tokens. The helpers also work without the fixtures:
`check_compactor(compactor, rounds=5, budget_fraction=0.2)` returns
a report, and `assert_no_flags`, `assert_budget_compliant`, and
`assert_type_survival` turn verdicts into test failures. Fixtures
for the raw materials are included too: `seeded_session` and
`seeded_canaries`.

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
