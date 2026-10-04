from __future__ import annotations

from dataclasses import dataclass

from .canaries import Canary


def _holds(text_lower: str, tokens: tuple[str, ...]) -> bool:
    """A canary is held when every required token survives in the context.

    Strict by design: partial survival (e.g. 'budget' without '$500') is a
    loss, because the rule no longer constrains behavior.
    """
    return all(tok.lower() in text_lower for tok in tokens)


@dataclass(frozen=True)
class ProbeResult:
    canary_id: str
    direct_pass: bool
    behavior_pass: bool | None  # None when no behavior probe applies

    @property
    def survived(self) -> bool:
        if self.behavior_pass is None:
            return self.direct_pass
        return self.direct_pass and self.behavior_pass


class DirectRecallProbe:
    """Does the compacted context still contain the canary's content?

    Framework-agnostic: against a live agent this becomes 'ask the direct
    question and grade the answer'; against a compacted-context string it
    is a containment check. Both answer the same question — is the
    information still available to the agent.
    """

    name = "direct-recall"

    def probe(self, canary: Canary, context_text: str) -> ProbeResult:
        held = _holds(context_text.lower(), canary.required_tokens)
        return ProbeResult(canary_id=canary.id, direct_pass=held, behavior_pass=None)


class BehaviorProbe:
    """Would the agent still act correctly in the canary's scenario?

    For the spike this is evaluated against the compacted context: the
    blocking rule must be present for the correct action to be taken.
    A live-agent adapter swaps in scenario execution without changing
    the runner or report.
    """

    name = "behavior"

    def probe(self, canary: Canary, context_text: str) -> ProbeResult:
        lower = context_text.lower()
        direct = _holds(lower, canary.required_tokens)
        if not canary.behavior_scenario:
            return ProbeResult(canary_id=canary.id, direct_pass=direct, behavior_pass=None)
        behavior = _holds(lower, canary.behavior_required_tokens)
        return ProbeResult(canary_id=canary.id, direct_pass=direct, behavior_pass=behavior)
