"""Fixed-budget benchmark run.

Runs every built-in compactor at 10%, 20%, and 30% output budgets over
the randomized corpus and both semantic corpora (8 seeds, 5 rounds),
and writes examples/budget-benchmark-results.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit.benchmark import budget_benchmark_to_markdown, run_budget_benchmark
from compaction_kit.cli import COMPACTORS

SEEDS = list(range(1, 9))
BUDGETS = [0.10, 0.20, 0.30]
ROUNDS = 5


def main() -> None:
    payload = run_budget_benchmark(
        COMPACTORS, budgets=BUDGETS, seeds=SEEDS, rounds=ROUNDS
    )
    out = Path(__file__).resolve().parents[1] / "examples" / "budget-benchmark-results.json"
    out.write_text(json.dumps(payload, indent=2))
    print(budget_benchmark_to_markdown(payload))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
