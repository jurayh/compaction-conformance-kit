# Examples and demos

Every demo runs with no API key and no model calls.

## Start here

| Demo | Command | What it shows |
| --- | --- | --- |
| 30-second CLI demo | `compaction-kit demo` | Three compactors, five rounds, per-type reports on the seeded session |
| CI gate | `compaction-kit report --compactor update-aware-checklist` | Exit 0 when clean, exit 1 on FLAG or late cliff |
| Randomized corpus | `compaction-kit corpus --seeds 1-12` | Survival medians across 12 generated sessions, JSON output |
| Measure your own compactor | `python3 examples/measure_your_compactor.py` | A custom compactor in about 20 lines, scored by the kit |
| Recorded CLI output | [demo_cli.md](demo_cli.md) | Verbatim output of the three commands above |

## Reports and data

| File | What it is |
| --- | --- |
| `report-lossy-truncation.md` | Seeded-session report: truncation flagged on 4 types |
| `report-naive-summary.md` | Seeded-session report: naive summary flagged on all 5 |
| `report-checklist-carrying.md` | Seeded-session report: checklist silent on all 5 |
| `spike-results.json` | The three seeded reports plus kill-criterion checks, as JSON |
| `corpus-results.json` | 12-seed corpus aggregates: survival, cliffs, position effect, supersession |
| `mitigations-results.json` | Six-compactor mitigation comparison aggregates |

## Longer write-ups

- [../sim/BLIND_SIMULATION.md](../sim/BLIND_SIMULATION.md) — blind agents
  answer probes from compacted text only; the $0 token probe predicts
  them 20/20.
- [../sim/FREEFORM_SUMMARIZER.md](../sim/FREEFORM_SUMMARIZER.md) — a real
  LLM summarizing freely holds 100% for two rounds, loses every safety
  rule at round 3, and falls to 10% by round 5.
- [../sim/CORPUS.md](../sim/CORPUS.md) — the multi-seed corpus test and
  the over-preservation (stale value) problem.
- [../sim/MITIGATIONS.md](../sim/MITIGATIONS.md) — which mitigation
  actually works: update-aware checklist wins on both axes.
