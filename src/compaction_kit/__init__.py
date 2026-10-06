"""Compaction conformance kit.

Measures what an agent's context compaction actually preserves,
by planting typed canaries and probing survival across rounds.
"""

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
from .probes import BehaviorProbe, DirectRecallProbe, ExactUseProbe, ProbeResult
from .report import ConformanceReport, build_report
from .runner import RoundResult, run_conformance
from .semantic import SemanticChecklistCompactor
from .semantic_corpus import build_semantic_heldout_session, build_semantic_session
from .session import SeededSession, Turn, build_seeded_session
from .simulated_agent import SimulatedAgent, SimulatedAnswer

__all__ = [
    "BehaviorProbe",
    "Canary",
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
    "ProbeResult",
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
    "position_bucket",
    "run_budget_benchmark",
    "run_conformance",
    "seeded_canaries",
]
