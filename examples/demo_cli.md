# Recorded CLI demos

Generated with the installed `compaction-kit` CLI (demo output abbreviated).

## compaction-kit demo --compactor lossy-truncation (abbreviated)

Exit code: 0

```text
# Compaction conformance report — lossy-truncation

| Type | Round 1 | Curve (rounds 1..n) | Round-1 verdict | Cliff round | Final |
| --- | --- | --- | --- | --- | --- |
| safety_rule | 25% | 25%, 0%, 0% | FLAG | 1 | 0% |
| hard_constraint | 25% | 25%, 0%, 0% | FLAG | 1 | 0% |
| fact | 25% | 25%, 0%, 0% | FLAG | 1 | 0% |
| goal_state | 50% | 50%, 25%, 0% | WARN | 2 | 0% |
| user_preference | 25% | 25%, 0%, 0% | FLAG | 1 | 0% |

Flag threshold: below 50% survival. Silent above 90% after round 1. Cliff round is the first round a type falls below the flag threshold.
FLAGGED at round 1: safety_rule, hard_constraint, fact, user_preference
LATE CLIFF (passed round 1, fell below threshold later): goal_state at round 2
```

## compaction-kit report --compactor update-aware-checklist

Exit code: 0

```text
# Compaction conformance report — update-aware-checklist

| Type | Round 1 | Curve (rounds 1..n) | Round-1 verdict | Cliff round | Final |
| --- | --- | --- | --- | --- | --- |
| safety_rule | 100% | 100%, 100%, 100% | SILENT | — | 100% |
| hard_constraint | 100% | 100%, 100%, 100% | SILENT | — | 100% |
| fact | 100% | 100%, 100%, 100% | SILENT | — | 100% |
| goal_state | 100% | 100%, 100%, 100% | SILENT | — | 100% |
| user_preference | 100% | 100%, 100%, 100% | SILENT | — | 100% |

Flag threshold: below 50% survival. Silent above 90% after round 1. Cliff round is the first round a type falls below the flag threshold.
```

## compaction-kit corpus --compactor update-aware-checklist --seeds 1-3

Exit code: 0

```text
{
  "seeds": [
    1,
    2,
    3
  ],
  "rounds": 3,
  "by_compactor": {
    "update-aware-checklist": {
      "round1_median_by_type": {
        "fact": 1.0,
        "goal_state": 1.0,
        "hard_constraint": 1.0,
        "safety_rule": 1.0,
        "user_preference": 1.0
      },
      "final_median_by_type": {
        "fact": 1.0,
        "goal_state": 1.0,
        "hard_constraint": 1.0,
        "safety_rule": 1.0,
        "user_preference": 1.0
      },
      "supersession": {
        "r-constraint-1": {
          "n": 3,
          "latest": 3,
          "stale": 0,
          "both": 0,
          "stale_only": 0
        },
        "r-fact-1": {
          "n": 3,
          "latest": 3,
          "stale": 0,
          "both": 0,
          "stale_only": 0
        }
      }
    }
  }
}
```
