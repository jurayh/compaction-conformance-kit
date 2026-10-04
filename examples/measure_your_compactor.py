#!/usr/bin/env python3
"""Measure your own compaction in about 20 lines.

Replace `first_paragraph_summary` with your real compaction (an LLM
summarizer call, your framework's /compact, a sliding window) and the
kit reports what it preserves. Run:

    pip install compaction-conformance-kit
    python3 examples/measure_your_compactor.py
"""

from compaction_kit.compacted import CompactedContext
from compaction_kit.report import build_report
from compaction_kit.runner import run_conformance
from compaction_kit.session import build_seeded_session


def first_paragraph_summary(text: str) -> str:
    """Toy stand-in for a real summarizer: keep the opening, gist the rest."""
    head = text[:600]
    return head + "\n[rest of session summarized away]"


class MyCompactor:
    name = "my-compaction"

    def compact(self, turns, round_num=1):
        text = "\n".join(f"[{t.role}] {t.text}" for t in turns)
        return CompactedContext(
            text=first_paragraph_summary(text),
            compactor_name=self.name,
            round_num=round_num,
        )


if __name__ == "__main__":
    run = run_conformance(build_seeded_session(), MyCompactor(), rounds=5)
    report = build_report(run)
    print(report.to_markdown())
    print("Flagged at round 1:", report.flagged_types or "none")
    print("Late cliffs:", report.late_cliff_types or "none")
