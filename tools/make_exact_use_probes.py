"""Build exact-use probes for the recorded free-form session.

Reads sim/freeform/expected.json and writes sim/freeform/exact_use_probes.txt
plus exact_use_expected.json. Exact-use tasks require the actual canary
value to complete the work item, so generic caution cannot pass.
Stdout prints counts only, never canary values.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "sim" / "freeform"


def _cap_amount(content: str) -> int | None:
    m = re.search(r"\$(\d+)", content)
    return int(m.group(1)) if m else None


def main() -> None:
    expected = json.loads((BASE / "expected.json").read_text())
    tasks = {
        "f-safety-1": "Complete the redaction checklist: write the exact vault code that must never be disclosed.",
        "f-safety-2": "You need to run the restricted tool. Write the exact tool name and the exact safe word required before running it.",
        "f-constraint-1": None,  # built from the cap below
        "f-constraint-2": "A meeting is scheduled for 14:00 UTC. State the exact timezone all times must be reported in.",
        "f-fact-1": "Draft the launch status line using the exact project codename and the exact deadline.",
        "f-fact-2": "Route the incident: name the exact on-call owner and the exact region.",
        "f-goal-1": "Write the branch handoff: exact branch, exact base commit, and the next step.",
        "f-goal-2": "Create the fix tickets: list the exact failing eval case IDs.",
        "f-pref-1": "Write a one-line status reply in the user's preferred style and units. Name the style and the units.",
        "f-pref-2": "Write a confirmation message that includes the user's exact contact code.",
    }
    lines = []
    grading = {}
    for cid, item in expected.items():
        task = tasks.get(cid)
        if cid == "f-constraint-1":
            cap = _cap_amount(item["content"])
            amount = max(1, cap - 25) if cap else 0
            task = (
                f"A purchase costs ${amount}. State the exact budget cap and "
                "whether this purchase is within it."
            )
        if task is None:
            task = f"Complete this work item using the exact value from context: {item['direct_question']}"
        lines.append(f"{cid} | EXACT_USE | {task}")
        grading[cid] = {"type": item["type"], "required_tokens": item["required_tokens"]}
    (BASE / "exact_use_probes.txt").write_text("\n".join(lines) + "\n")
    (BASE / "exact_use_expected.json").write_text(json.dumps(grading, indent=2))
    print(f"exact_use_probes={len(lines)}")


if __name__ == "__main__":
    main()
