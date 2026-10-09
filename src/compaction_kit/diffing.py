"""Compare two conformance reports and gate on regressions.

`compaction-kit diff baseline.json current.json` answers the CI
question: did this change make compaction worse? A type regresses
when it newly crosses the flag threshold, gains a cliff (or its
cliff moves earlier), or loses at least 25 points of round-1 or
final survival. Improvements are reported but never fail the gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_DROP = 0.25


@dataclass
class TypeDiff:
    canary_type: str
    regressions: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)

    @property
    def regressed(self) -> bool:
        return bool(self.regressions)


@dataclass
class ReportDiff:
    baseline_compactor: str
    current_compactor: str
    types: list[TypeDiff] = field(default_factory=list)

    @property
    def regressed_types(self) -> list[str]:
        return [t.canary_type for t in self.types if t.regressed]

    @property
    def has_regressions(self) -> bool:
        return bool(self.regressed_types)

    def to_markdown(self) -> str:
        lines = [
            f"# Conformance diff — {self.baseline_compactor} → {self.current_compactor}",
            "",
        ]
        if not self.types:
            lines.append("No comparable types in the two reports.")
            return "\n".join(lines) + "\n"
        lines += ["| Type | Result | Detail |", "| --- | --- | --- |"]
        for t in self.types:
            if t.regressions:
                result, detail = "REGRESSION", "; ".join(t.regressions)
            elif t.improvements:
                result, detail = "improved", "; ".join(t.improvements)
            else:
                result, detail = "unchanged", "—"
            lines.append(f"| {t.canary_type} | {result} | {detail} |")
        lines.append("")
        if self.has_regressions:
            lines.append(f"REGRESSED: {', '.join(self.regressed_types)}")
        else:
            lines.append("No regressions.")
        return "\n".join(lines) + "\n"


def _findings_by_type(payload: dict) -> dict[str, dict]:
    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise ValueError("report JSON must contain a 'findings' list")
    return {f["type"]: f for f in findings}


def diff_reports(baseline: dict, current: dict) -> ReportDiff:
    old = _findings_by_type(baseline)
    new = _findings_by_type(current)
    diff = ReportDiff(
        baseline_compactor=str(baseline.get("compactor", "baseline")),
        current_compactor=str(current.get("compactor", "current")),
    )
    for canary_type in sorted(set(old) | set(new)):
        td = TypeDiff(canary_type=canary_type)
        if canary_type not in old:
            td.improvements.append("type newly reported")
            diff.types.append(td)
            continue
        if canary_type not in new:
            td.regressions.append("type missing from current report")
            diff.types.append(td)
            continue
        o, n = old[canary_type], new[canary_type]
        if n["verdict"] == "FLAG" and o["verdict"] != "FLAG":
            td.regressions.append(f"verdict {o['verdict']} → FLAG")
        if o["verdict"] == "FLAG" and n["verdict"] != "FLAG":
            td.improvements.append(f"verdict FLAG → {n['verdict']}")
        o_cliff, n_cliff = o.get("cliff_round"), n.get("cliff_round")
        if n_cliff is not None and (o_cliff is None or n_cliff < o_cliff):
            td.regressions.append(f"cliff at round {n_cliff} (was {o_cliff or 'none'})")
        if o_cliff is not None and n_cliff is None:
            td.improvements.append("cliff removed")
        for key, label in (("round1_survival", "round-1"), ("final_survival", "final")):
            delta = n[key] - o[key]
            if delta <= -_DROP:
                td.regressions.append(f"{label} survival {o[key]:.0%} → {n[key]:.0%}")
            elif delta >= _DROP:
                td.improvements.append(f"{label} survival {o[key]:.0%} → {n[key]:.0%}")
        diff.types.append(td)
    return diff
