"""Generate the README survival chart from the corpus runs.

Safety-rule survival (median across seeds 1-12) per compactor, rounds
1-5, as a dependency-free SVG. Output: docs/assets/safety-survival.svg
"""

from __future__ import annotations

import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compaction_kit.compactors import (
    ChecklistCompactor,
    LossyTruncationCompactor,
    NaiveSummaryCompactor,
    PinnedRulesCompactor,
    SummaryTailCompactor,
    UpdateAwareChecklistCompactor,
)
from compaction_kit.corpus import build_random_session
from compaction_kit.runner import run_conformance

COMPACTORS = [
    ("lossy-truncation", LossyTruncationCompactor, "#c0392b"),
    ("naive-summary", NaiveSummaryCompactor, "#e67e22"),
    ("summary-plus-tail", SummaryTailCompactor, "#8e44ad"),
    ("pinned-rules", PinnedRulesCompactor, "#2980b9"),
    ("checklist-carrying", ChecklistCompactor, "#27ae60"),
    ("update-aware-checklist", UpdateAwareChecklistCompactor, "#16a085"),
]
# TOP reserves a header band for the title and the two legend rows, so the
# 100% line (at y=TOP) clears the legend instead of running through it.
W, H, PAD, TOP = 760, 416, 56, 112


def main() -> None:
    series: dict[str, list[float]] = {}
    for name, cls, _ in COMPACTORS:
        per_round: dict[int, list[float]] = defaultdict(list)
        for seed in range(1, 13):
            session, canaries = build_random_session(seed)
            run = run_conformance(session, cls(), rounds=5, canaries=canaries)
            for r in run.rounds:
                per_round[r.round_num].append(r.survival_by_type["safety_rule"])
        series[name] = [statistics.median(per_round[i]) for i in range(1, 6)]

    def x(i: int) -> float:
        return PAD + i * (W - 2 * PAD) / 4

    def y(v: float) -> float:
        return H - PAD - v * (H - PAD - TOP)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="380" y="24" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold">Safety-rule survival across compaction rounds</text>',
        '<text x="380" y="42" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#555">Median across 12 randomized sessions, 4 safety canaries each</text>',
    ]
    for v in (0, 0.25, 0.5, 0.75, 1.0):
        parts.append(f'<line x1="{PAD}" y1="{y(v):.1f}" x2="{W-PAD}" y2="{y(v):.1f}" stroke="#ddd"/>')
        parts.append(f'<text x="{PAD-8}" y="{y(v)+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="10">{v:.0%}</text>')
    # 50% flag line
    parts.append(f'<line x1="{PAD}" y1="{y(0.5):.1f}" x2="{W-PAD}" y2="{y(0.5):.1f}" stroke="#c0392b" stroke-dasharray="4 3"/>')
    parts.append(f'<text x="{W-PAD}" y="{y(0.5)-6:.1f}" text-anchor="end" font-family="sans-serif" font-size="10" fill="#c0392b">FLAG below 50%</text>')
    for i in range(5):
        parts.append(f'<text x="{x(i):.1f}" y="{H-PAD+18}" text-anchor="middle" font-family="sans-serif" font-size="10">round {i+1}</text>')
    for idx, (name, _cls, color) in enumerate(COMPACTORS):
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(series[name]))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5"/>')
        for i, v in enumerate(series[name]):
            parts.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3.5" fill="{color}"/>')
        lx, ly = PAD + 10 + (idx % 3) * 235, 58 + (idx // 3) * 16
        parts.append(f'<line x1="{lx}" y1="{ly-4}" x2="{lx+22}" y2="{ly-4}" stroke="{color}" stroke-width="2.5"/>')
        parts.append(f'<text x="{lx+28}" y="{ly}" font-family="sans-serif" font-size="11">{name}</text>')
    parts.append("</svg>")
    out = Path(__file__).resolve().parents[1] / "docs" / "assets" / "safety-survival.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts) + "\n")
    print(f"wrote {out}")
    for name, vals in series.items():
        print(name, [f"{v:.0%}" for v in vals])


if __name__ == "__main__":
    main()
