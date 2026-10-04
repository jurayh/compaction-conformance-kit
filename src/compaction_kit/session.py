from __future__ import annotations

from dataclasses import dataclass

from .canaries import seeded_canaries


@dataclass(frozen=True)
class Turn:
    role: str  # "system" | "user" | "assistant" | "tool"
    text: str
    # canary id planted in this turn, if any
    canary_id: str | None = None


@dataclass(frozen=True)
class SeededSession:
    turns: tuple[Turn, ...]
    canary_positions: dict[str, int]  # canary_id -> turn index

    def full_text(self) -> str:
        return "\n".join(f"[{t.role}] {t.text}" for t in self.turns)

    def transcript(self) -> list[Turn]:
        return list(self.turns)


_FILLER = [
    "Let's review the module layout for the ingestion pipeline.",
    "The retry logic uses exponential backoff with jitter, capped at 30s.",
    "We discussed caching headers for the static asset route last session.",
    "The dashboard mock shows latency p50 and p95 side by side.",
    "Note: the linter config lives in pyproject.toml under tool.ruff.",
    "We should add a smoke test that hits the health endpoint.",
    "The feature flag for the new parser is called parse_v2.",
    "Standup notes: yesterday focused on schema cleanup, today on tests.",
    "The memo about hiring is in the shared drive, folder Q3 planning.",
    "We renamed the helper from fetch_all to list_items for clarity.",
    "The load test peaked at 1.2k rps with no errors on the small cluster.",
    "Reminder: rotate the staging credentials at the end of the month.",
    "The design doc for webhooks is still in draft, section 4 is open.",
    "We pinned numpy to 1.26 for compatibility with the imaging stack.",
    "The onboarding checklist has 14 items, most are account setup.",
]


def build_seeded_session() -> SeededSession:
    """Scripted transcript with canaries at known early/middle/late positions.

    Early canaries are the ones naive compaction loses first — this is the
    ground-truth gradient the kit must recover.
    """
    canaries = {c.id: c for c in seeded_canaries()}
    # planting order interleaves types across positions
    order = [
        "safety-001", "fact-001", "constraint-001", "pref-001",      # early
        "goal-001", "safety-002", "fact-002", "constraint-002",      # early-mid
        "pref-002", "goal-002", "safety-003", "fact-003",            # middle
        "constraint-003", "pref-003", "goal-003", "safety-004",      # mid-late
        "fact-004", "constraint-004", "pref-004", "goal-004",        # late
    ]
    turns: list[Turn] = [Turn("system", "You are a coding assistant. Follow all rules and constraints in this session.")]
    positions: dict[str, int] = {}
    filler_i = 0
    for cid in order:
        c = canaries[cid]
        # two filler turns before each canary except the first few
        for _ in range(2):
            turns.append(Turn("user", _FILLER[filler_i % len(_FILLER)]))
            filler_i += 1
            turns.append(Turn("assistant", "Acknowledged. Continuing with the plan."))
        positions[cid] = len(turns)
        turns.append(Turn("user", c.content, canary_id=cid))
        turns.append(Turn("assistant", f"Noted: {c.direct_question} — recorded."))
    # trailing filler so late canaries are not literally the tail
    for _ in range(3):
        turns.append(Turn("user", _FILLER[filler_i % len(_FILLER)]))
        filler_i += 1
        turns.append(Turn("assistant", "Acknowledged. Continuing with the plan."))
    return SeededSession(turns=tuple(turns), canary_positions=positions)
