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
    exact_use_pass: bool | None = None  # None when no exact-use probe applies

    @property
    def survived(self) -> bool:
        if not self.direct_pass:
            return False
        if self.behavior_pass is not None and not self.behavior_pass:
            return False
        if self.exact_use_pass is not None and not self.exact_use_pass:
            return False
        return True


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
        exact = (
            _holds(lower, canary.exact_use_required_tokens)
            if canary.exact_use_scenario
            else None
        )
        if not canary.behavior_scenario:
            return ProbeResult(
                canary_id=canary.id, direct_pass=direct, behavior_pass=None, exact_use_pass=exact
            )
        behavior = _holds(lower, canary.behavior_required_tokens)
        return ProbeResult(
            canary_id=canary.id, direct_pass=direct, behavior_pass=behavior, exact_use_pass=exact
        )


class ExactUseProbe:
    """Can the agent complete work that requires the exact canary value?

    Refusal-friendly behavior scenarios can pass on generic caution after
    the exact value is gone ('restrictions remain in force'). An exact-use
    item cannot: deciding whether a purchase fits requires the cap,
    routing a page requires the owner's name, a handoff requires the base
    commit. This probe grades whether the exact values needed to complete
    the item survive in the context.
    """

    name = "exact-use"

    def probe(self, canary: Canary, context_text: str) -> ProbeResult:
        lower = context_text.lower()
        direct = _holds(lower, canary.required_tokens)
        if not canary.exact_use_scenario:
            return ProbeResult(canary_id=canary.id, direct_pass=direct, behavior_pass=None)
        exact = _holds(lower, canary.exact_use_required_tokens)
        return ProbeResult(
            canary_id=canary.id, direct_pass=direct, behavior_pass=None, exact_use_pass=exact
        )
