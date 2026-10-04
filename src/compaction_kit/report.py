from __future__ import annotations

import json
from dataclasses import dataclass, field

from .canaries import CanaryType
from .runner import ConformanceRun

FLAG_BELOW = 0.50   # flag any type falling below 50% survival after round 1
SILENT_ABOVE = 0.90  # stay silent on types above 90%


@dataclass
class TypeFinding:
    canary_type: str
    round1_survival: float
    verdict: str  # "FLAG" | "WARN" | "SILENT"
    curve: list[float]


@dataclass
class ConformanceReport:
    compactor_name: str
    findings: list[TypeFinding] = field(default_factory=list)

    @property
    def flagged_types(self) -> list[str]:
        return [f.canary_type for f in self.findings if f.verdict == "FLAG"]

    @property
    def silent_types(self) -> list[str]:
        return [f.canary_type for f in self.findings if f.verdict == "SILENT"]

    def to_dict(self) -> dict:
        return {
            "compactor": self.compactor_name,
            "thresholds": {"flag_below": FLAG_BELOW, "silent_above": SILENT_ABOVE},
            "findings": [
                {
                    "type": f.canary_type,
                    "round1_survival": f.round1_survival,
                    "verdict": f.verdict,
                    "survival_curve": f.curve,
                }
                for f in self.findings
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_markdown(self) -> str:
        lines = [
            f"# Compaction conformance report — {self.compactor_name}",
            "",
            "| Type | Round 1 | Curve (rounds 1..n) | Verdict |",
            "| --- | --- | --- | --- |",
        ]
        for f in self.findings:
            curve = ", ".join(f"{v:.0%}" for v in f.curve)
            lines.append(f"| {f.canary_type} | {f.round1_survival:.0%} | {curve} | {f.verdict} |")
        lines += [
            "",
            f"Flag threshold: below {FLAG_BELOW:.0%} after round 1. "
            f"Silent above {SILENT_ABOVE:.0%}.",
        ]
        if self.flagged_types:
            lines.append(f"FLAGGED: {', '.join(self.flagged_types)}")
        return "\n".join(lines) + "\n"


def build_report(run: ConformanceRun) -> ConformanceReport:
    report = ConformanceReport(compactor_name=run.compactor_name)
    if not run.rounds:
        return report
    for ctype in CanaryType:
        curve = run.survival_curve(ctype)
        r1 = curve[0] if curve else 0.0
        if r1 < FLAG_BELOW:
            verdict = "FLAG"
        elif r1 > SILENT_ABOVE:
            verdict = "SILENT"
        else:
            verdict = "WARN"
        report.findings.append(
            TypeFinding(canary_type=ctype.value, round1_survival=r1, verdict=verdict, curve=curve)
        )
    return report
