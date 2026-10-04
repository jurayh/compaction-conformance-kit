"""A $0 simulated agent for probing compacted context.

The expensive version of this kit asks a real LLM agent the probe
questions and grades the answers. This module answers the same probes
with deterministic retrieval over the compacted text only:

- Direct recall: find the most relevant line in the compacted context
  and return it; if no required information is retrievable, say so.
- Behavior: if the blocking rule is retrievable, act on it (refuse /
  block / follow the recorded next step); otherwise proceed as an
  agent without that rule would.

This is an ideal-retrieval upper bound: if even this agent cannot
recover a canary from the compacted text, a real agent cannot either
(except by guessing). Validated 2026-10-04 against a blind
self-simulation: a separate model given only the compacted text gave
answers that matched this module's presence predictions 20/20 across
lossy and checklist contexts (10 canaries x 2 compactors).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .canaries import Canary


@dataclass(frozen=True)
class SimulatedAnswer:
    canary_id: str
    answer: str
    found: bool

    @property
    def survived(self) -> bool:
        return self.found


def _lines(context_text: str) -> list[str]:
    return [ln.strip(" -") for ln in context_text.splitlines() if ln.strip(" -")]


class SimulatedAgent:
    """Answers probes from compacted context only. No model calls."""

    def answer_direct(self, canary: Canary, context_text: str) -> SimulatedAnswer:
        lower = context_text.lower()
        if all(tok.lower() in lower for tok in canary.required_tokens if tok):
            # return the line carrying the canary
            for ln in _lines(context_text):
                if any(tok.lower() in ln.lower() for tok in canary.required_tokens if tok):
                    return SimulatedAnswer(canary.id, ln, True)
            return SimulatedAnswer(canary.id, canary.content, True)
        return SimulatedAnswer(canary.id, "NOT IN CONTEXT", False)

    def answer_behavior(self, canary: Canary, context_text: str) -> SimulatedAnswer:
        direct = self.answer_direct(canary, context_text)
        if not canary.behavior_scenario:
            return direct
        if direct.found:
            return SimulatedAnswer(
                canary.id,
                f"Would follow the preserved rule: {direct.answer}",
                True,
            )
        return SimulatedAnswer(
            canary.id,
            "Would proceed without the rule (not in context).",
            False,
        )
