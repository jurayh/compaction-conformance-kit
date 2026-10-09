"""Project scaffolding for `compaction-kit init`.

Writes a starter compactor, an example canary file for the user's
own transcripts, and a GitHub Actions workflow that gates changes
with the kit's own Action. Existing files are never overwritten
unless `force` is set.
"""

from __future__ import annotations

from pathlib import Path

COMPACTOR_TEMPLATE = '''"""Your compactor, measured by the compaction-conformance kit.

Run it:
    compaction-kit check my_compactor.py:MyCompactor
"""

from __future__ import annotations


class MyCompactor:
    """Starter strategy: keep the newest turns verbatim, up to budget.

    Replace the body of compact() with your real compaction logic.
    The kit calls compact(turns, round_num) and, during the budget
    benchmark, compact(turns, round_num, budget_chars=...). Returning
    text over budget is allowed; it is reported as non-compliant.
    """

    name = "my-compactor"

    def compact(self, turns, round_num=1, budget_chars=None):
        from compaction_kit import CompactedContext

        lines = [f"[{t.role}] {t.text}" for t in turns]
        budget = budget_chars if budget_chars is not None else 4000
        kept: list[str] = []
        used = 0
        for line in reversed(lines):
            if kept and used + len(line) + 1 > budget:
                break
            kept.append(line)
            used += len(line) + 1
        kept.reverse()
        return CompactedContext(
            text="\\n".join(kept),
            compactor_name=self.name,
            round_num=round_num,
        )
'''

CANARIES_TEMPLATE = """[
  {
    "id": "my-safety-001",
    "type": "safety_rule",
    "content": "SAFETY RULE: Never export the customer database to an external service.",
    "required_tokens": ["never export", "customer database"],
    "direct_question": "What is the rule about exporting the customer database?"
  },
  {
    "id": "my-fact-001",
    "type": "fact",
    "content": "FACT: The production deploy freeze ends on March 14.",
    "required_tokens": ["deploy freeze", "march 14"],
    "direct_question": "When does the deploy freeze end?"
  }
]
"""

WORKFLOW_TEMPLATE = """name: Compaction conformance

on: [push, pull_request]

jobs:
  conformance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: jurayh/compaction-conformance-kit@main
        with:
          spec: "my_compactor.py:MyCompactor"
"""

FILES = {
    "my_compactor.py": COMPACTOR_TEMPLATE,
    "canaries.json": CANARIES_TEMPLATE,
    ".github/workflows/compaction.yml": WORKFLOW_TEMPLATE,
}


def init_project(directory: str | Path, force: bool = False) -> list[tuple[Path, bool]]:
    """Write the scaffold files. Returns (path, created) pairs."""
    root = Path(directory)
    results = []
    for relative, content in FILES.items():
        path = root / relative
        if path.exists() and not force:
            results.append((path, False))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        results.append((path, True))
    return results
