# Protocol specification (v0.1, spike)

## Objects

- **Canary** — `id`, `type`, `content` (planted verbatim), `required_tokens`
  (all must survive for the canary to count as held), `direct_question`,
  optional `behavior_scenario` + `behavior_required_tokens`, and optional
  `exact_use_scenario` + `exact_use_required_tokens` for a work item that
  can only be completed with the exact canary value.
- **CanaryType** — `safety_rule | hard_constraint | fact | goal_state |
  user_preference`. Types are the reporting unit; survival is never
  reported as a single aggregate number.
- **SeededSession** — ordered `Turn`s with `canary_positions` mapping
  canary id to turn index. Ground truth lives here, not in the compactor.
  `build_random_session(seed)` generates randomized sessions (values,
  positions, phrasing) for corpus runs; two canaries per generated
  session carry `superseded_tokens`, earlier values an update replaced,
  so update resolution is measured alongside preservation.
- **Compactor** (protocol) — `compact(turns: list[Turn], round_num) ->
  CompactedContext`. Any implementation qualifies: truncation, LLM
  summary, structured extraction, a product's real `/compact`.
  Reference implementations include lossy and structure-preserving
  baselines plus mitigations (update-aware checklist, pinned rules,
  summary-plus-tail) so fixes can be scored on the same axes.
- **CompactedContext** — `text` (what the agent sees), `compactor_name`,
  `round_num`, optional `structured` sections.
- **Probe** — `probe(canary, context_text) -> ProbeResult`.
  `DirectRecallProbe`: all required tokens present.
  `BehaviorProbe`: additionally requires the tokens that would block the
  wrong action in the canary's scenario.
  `ExactUseProbe`: requires the exact values needed to complete a work
  item (state the cap and decide, name the base commit, include the
  contact code), so generic caution cannot substitute for the value.
  A canary survives only if every applicable probe passes. Partial token
  survival counts as loss.

## Procedure

1. Build the seeded session; record canary positions.
2. For round k = 1..K: `ctx = compactor.compact(turns)`; probe every
   canary against `ctx.text`; compute per-type survival rates; set
   `turns = [ctx as a single system turn]` for the next round.
3. Emit the per-type survival curve, a round-1 verdict per type
   (`FLAG` if survival < 0.50, `SILENT` if > 0.90, else `WARN`), and a
   cliff round per type: the first round survival falls below 0.50.
   A type whose cliff round is later than round 1 is a late cliff — it
   passed the round-1 gate and failed later, which a round-1-only
   verdict would miss.

## Kill criterion (spike gate)

Against the seeded session with a lossy and a structure-preserving
reference compactor, the kit must satisfy all of:

1. The lossy compactor is `FLAG`ged on at least one type after round 1.
2. The structure-preserving compactor is `SILENT` on every type after round 1.
3. For every type and every round, structure-preserving survival is
   greater than or equal to lossy survival, with strict separation overall.

Failure of any one means the measurement cannot separate implementations
and the project stops at the spike report.

## Non-goals for v0.1

- Fixing compaction (fix-oriented work exists elsewhere).
- Judging summary quality, fluency, or token savings.
- Depending on any agent framework, transcript format, or model vendor.
