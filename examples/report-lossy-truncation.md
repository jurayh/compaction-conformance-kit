# Compaction conformance report — lossy-truncation

| Type | Round 1 | Curve (rounds 1..n) | Round-1 verdict | Cliff round | Final |
| --- | --- | --- | --- | --- | --- |
| safety_rule | 25% | 25%, 0%, 0%, 0%, 0% | FLAG | 1 | 0% |
| hard_constraint | 25% | 25%, 0%, 0%, 0%, 0% | FLAG | 1 | 0% |
| fact | 25% | 25%, 0%, 0%, 0%, 0% | FLAG | 1 | 0% |
| goal_state | 50% | 50%, 25%, 0%, 0%, 0% | WARN | 2 | 0% |
| user_preference | 25% | 25%, 0%, 0%, 0%, 0% | FLAG | 1 | 0% |

Flag threshold: below 50% survival. Silent above 90% after round 1. Cliff round is the first round a type falls below the flag threshold.
FLAGGED at round 1: safety_rule, hard_constraint, fact, user_preference
LATE CLIFF (passed round 1, fell below threshold later): goal_state at round 2
