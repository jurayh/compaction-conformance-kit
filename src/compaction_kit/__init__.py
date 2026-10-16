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
from .generated import build_generated_session
from .diagnosis import CanaryDiagnosis, diagnose_run
from .diffing import ReportDiff, diff_reports
from .loading import load_compactor, load_compactor_factory
from .probes import BehaviorProbe, DirectRecallProbe, ExactUseProbe, ProbeResult
from .report import (
    BudgetCheck,
    BudgetRoundResult,
    ConformanceReport,
    budget_check_from_run,
    build_report,
)
from .runner import RoundResult, run_conformance
from .scaffold import init_project
from .semantic import SemanticChecklistCompactor
from .semantic_corpus import build_semantic_heldout_session, build_semantic_session
from .session import SeededSession, Turn, build_seeded_session
from .simulated_agent import SimulatedAgent, SimulatedAnswer
from .versioning import SCHEMA_VERSION, kit_version
from .testing import (
    assert_budget_compliant,
    assert_no_flags,
    assert_type_survival,
    check_compactor,
)
from .transcripts import (
    build_transcript_session,
    load_canaries,
    load_transcript,
    score_compacted_output,
)

__all__ = [
    "SCHEMA_VERSION",
    "BehaviorProbe",
    "BudgetCheck",
    "BudgetRoundResult",
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
    "assert_budget_compliant",
    "assert_no_flags",
    "assert_type_survival",
    "build_generated_session",
    "build_random_session",
    "build_semantic_heldout_session",
    "build_semantic_session",
    "build_report",
    "build_seeded_session",
    "build_transcript_session",
    "budget_benchmark_to_markdown",
    "budget_check_from_run",
    "check_compactor",
    "diagnose_run",
    "diff_reports",
    "init_project",
    "kit_version",
    "load_canaries",
    "load_compactor",
    "load_compactor_factory",
    "load_transcript",
    "position_bucket",
    "run_budget_benchmark",
    "run_conformance",
    "score_compacted_output",
    "seeded_canaries",
]
