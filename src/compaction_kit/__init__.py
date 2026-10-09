"""Compaction conformance kit.

Measures what an agent's context compaction actually preserves,
by planting typed canaries and probing survival across rounds.
"""

from .adapters import PrecomputedCompactor, ProgressiveSummaryCompactor
from .benchmark import budget_benchmark_to_markdown, run_budget_benchmark
from .canaries import Canary, CanaryType, seeded_canaries
from .compacted import CompactedContext
from .compactors import (
    ChecklistCompactor,
    Compactor,
    LLMSummarizerCompactor,
    LossyTruncationCompactor,
    NaiveSummaryCompactor,
    PinnedRulesCompactor,
    SummaryTailCompactor,
    UpdateAwareChecklistCompactor,
)
from .corpus import build_random_session, position_bucket
from .diagnosis import CanaryDiagnosis, diagnose_run
from .diffing import ReportDiff, diff_reports
from .loading import load_compactor
from .probes import BehaviorProbe, DirectRecallProbe, ExactUseProbe, ProbeResult
from .report import ConformanceReport, build_report
from .runner import RoundResult, run_conformance
from .scaffold import init_project
from .semantic import SemanticChecklistCompactor
from .semantic_corpus import build_semantic_heldout_session, build_semantic_session
from .session import SeededSession, Turn, build_seeded_session
from .simulated_agent import SimulatedAgent, SimulatedAnswer
from .transcripts import load_canaries, load_transcript, score_compacted_output

__all__ = [
    "BehaviorProbe",
    "Canary",
    "CanaryDiagnosis",
    "CanaryType",
    "ChecklistCompactor",
    "CompactedContext",
    "Compactor",
    "ConformanceReport",
    "DirectRecallProbe",
    "ExactUseProbe",
    "LLMSummarizerCompactor",
    "LossyTruncationCompactor",
    "NaiveSummaryCompactor",
    "PinnedRulesCompactor",
    "PrecomputedCompactor",
    "ProbeResult",
    "ProgressiveSummaryCompactor",
    "ReportDiff",
    "RoundResult",
    "SeededSession",
    "SemanticChecklistCompactor",
    "SimulatedAgent",
    "SimulatedAnswer",
    "SummaryTailCompactor",
    "Turn",
    "UpdateAwareChecklistCompactor",
    "build_random_session",
    "build_semantic_heldout_session",
    "build_semantic_session",
    "build_report",
    "build_seeded_session",
    "budget_benchmark_to_markdown",
    "diagnose_run",
    "diff_reports",
    "init_project",
    "load_canaries",
    "load_compactor",
    "load_transcript",
    "position_bucket",
    "run_budget_benchmark",
    "run_conformance",
    "score_compacted_output",
    "seeded_canaries",
]
