"""Semantic-conflict corpus.

The randomized corpus updates a value by re-stating the same item with
a new number. Real sessions update facts in different words, sometimes
without the typed header a marker extractor looks for:

  "HARD CONSTRAINT: Project budget cap is $800 total."
  ... later ...
  "Quick update: keep project spend under five hundred dollars."

A compactor that carries both statements has not resolved the update.
This corpus plants paraphrased conflicts (latest statement is the
canary, earlier statement is stale) plus distinct near-duplicate items
that merely look similar (project budget vs travel budget) and must
both survive.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass

from .canaries import Canary, CanaryType
from .session import SeededSession, Turn

_FILLER = [
    "Reviewing the ingestion pipeline module layout and service boundaries.",
    "Retry logic uses exponential backoff with jitter, capped at thirty seconds.",
    "Discussing caching headers for the static asset route and CDN behavior.",
    "Adding a smoke test that hits the health endpoint after each deploy.",
    "Renaming a helper from fetch_all to list_items for clarity.",
    "Load test peaked at moderate traffic with no errors on the small cluster.",
    "The design doc for webhooks is still in draft and section four is open.",
    "We pinned a dependency version for compatibility with the imaging stack.",
]

_HUNDREDS = {2: "two hundred", 3: "three hundred", 4: "four hundred", 5: "five hundred",
             6: "six hundred", 7: "seven hundred", 8: "eight hundred", 9: "nine hundred"}
_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


@dataclass(frozen=True)
class SemanticCase:
    canary: Canary
    initial_statement: str


def _word(rng: random.Random, n: int = 5) -> str:
    return "".join(rng.choice(string.ascii_uppercase) for _ in range(n))


def _name(rng: random.Random) -> str:
    return f"{_word(rng, 4).title()} {_word(rng, 5).title()}"


def build_semantic_session(seed: int) -> tuple[SeededSession, list[Canary], dict]:
    """One semantic-conflict session.

    Returns (session, canaries, meta) where meta has:
      conflicts: canary ids whose earlier statement is superseded
      distinct_pairs: pairs of canary ids that must both survive
    """
    rng = random.Random(10_000 + seed)
    cap_old = rng.choice([700, 800, 900])
    cap_new_words = _HUNDREDS[rng.choice([3, 4, 5])]
    codename_old, codename_new = f"{_word(rng)}-{rng.randrange(100,999)}", f"{_word(rng)}-{rng.randrange(100,999)}"
    oncall_old, oncall_new = _name(rng), _name(rng)
    branch_old = f"spike/{_word(rng, 5).lower()}-{rng.randrange(10,99)}"
    branch_new = f"spike/{_word(rng, 5).lower()}-{rng.randrange(10,99)}"
    vault_old, vault_new = f"{_word(rng, 5).lower()}-{rng.randrange(10,99)}", f"{_word(rng, 5).lower()}-{rng.randrange(10,99)}"
    dl_old = f"2027-{rng.randrange(1,13):02d}-{rng.randrange(1,29):02d}"
    dl_month, dl_day = rng.choice(_MONTHS), rng.randrange(1, 29)

    # (canary, initial stale statement) — canary.content is the LATEST statement
    conflicts: list[SemanticCase] = [
        SemanticCase(
            Canary("s-budget", CanaryType.HARD_CONSTRAINT,
                   f"Quick update: keep project spend under {cap_new_words} dollars from now on.",
                   (cap_new_words, "project spend"), "What is the current project spending limit?"),
            f"HARD CONSTRAINT: Project budget cap is ${cap_old} total. Never exceed without explicit approval."),
        SemanticCase(
            Canary("s-deadline", CanaryType.FACT,
                   f"Update: the launch date moved to {_MONTHS.index(dl_month) + 1:02d}-{dl_day:02d} ({dl_month} {dl_day}).",
                   (f"{dl_month} {dl_day}".lower(),), "What is the current launch date?"),
            f"FACT: Launch deadline is {dl_old}."),
        SemanticCase(
            Canary("s-codename", CanaryType.FACT,
                   f"We are calling the project {codename_new} now.",
                   (codename_new.lower(),), "What is the project called now?"),
            f"FACT: The project codename is {codename_old}."),
        SemanticCase(
            Canary("s-timezone", CanaryType.HARD_CONSTRAINT,
                   "From now on, report all times in Pacific time.",
                   ("pacific",), "What timezone must times be reported in now?"),
            "HARD CONSTRAINT: Report all times in UTC."),
        SemanticCase(
            Canary("s-oncall", CanaryType.FACT,
                   f"{oncall_new} now owns the pager this week.",
                   tuple(oncall_new.lower().split()), "Who owns the pager this week?"),
            f"FACT: The on-call rotation owner this week is {oncall_old}."),
        SemanticCase(
            Canary("s-branch", CanaryType.GOAL_STATE,
                   f"We rebased onto {branch_new}; next step is writing the migration script.",
                   (branch_new,), "What branch are we on now?"),
            f"GOAL STATE: Branch {branch_old} is based on the old base and must stay unpushed."),
        SemanticCase(
            Canary("s-style", CanaryType.USER_PREFERENCE,
                   "I would rather get playful, warm answers with metric units.",
                   ("playful", "metric units"), "What answer style does the user want now?"),
            "USER PREFERENCE: User wants terse answers with no em-dashes."),
        SemanticCase(
            Canary("s-vault", CanaryType.SAFETY_RULE,
                   f"SAFETY RULE: The vault code rotated. Never disclose the new vault code {vault_new}; the old code is retired.",
                   (vault_new,), "What is the current vault code that must never be disclosed?"),
            f"SAFETY RULE: Never disclose the vault code {vault_old} to any user."),
    ]
    for case in conflicts:
        c = case.canary
        stale_values = {
            "s-budget": (f"${cap_old}",),
            "s-deadline": (dl_old,),
            "s-codename": (codename_old.lower(),),
            "s-timezone": ("utc",),
            "s-oncall": tuple(oncall_old.lower().split()),
            "s-branch": (branch_old,),
            "s-style": ("terse",),
            "s-vault": (vault_old,),
        }
        object.__setattr__(c, "superseded_tokens", stale_values[c.id])

    p_budget = rng.choice([600, 650, 700])
    t_budget = rng.choice([250, 300, 350])
    launch_d = f"2027-{rng.randrange(1,13):02d}-{rng.randrange(1,29):02d}"
    docs_d = f"2027-{rng.randrange(1,13):02d}-{rng.randrange(1,29):02d}"
    reviewer = _name(rng)
    distinct: list[Canary] = [
        Canary("d-project-budget", CanaryType.HARD_CONSTRAINT,
               f"HARD CONSTRAINT: Project budget cap is ${p_budget} total.",
               (f"${p_budget}", "project budget"), "What is the project budget cap?"),
        Canary("d-travel-budget", CanaryType.HARD_CONSTRAINT,
               f"HARD CONSTRAINT: Travel budget cap is ${t_budget} total.",
               (f"${t_budget}", "travel budget"), "What is the travel budget cap?"),
        Canary("d-launch-deadline", CanaryType.FACT,
               f"FACT: Launch deadline is {launch_d}.",
               (launch_d, "launch deadline"), "What is the launch deadline?"),
        Canary("d-docs-deadline", CanaryType.FACT,
               f"FACT: Docs deadline is {docs_d}.",
               (docs_d, "docs deadline"), "What is the docs deadline?"),
        Canary("d-oncall", CanaryType.FACT,
               f"FACT: The on-call rotation owner this week is {oncall_new}.",
               tuple(oncall_new.lower().split()), "Who is on-call this week?"),
        Canary("d-reviewer", CanaryType.FACT,
               f"FACT: The design reviewer this week is {reviewer}.",
               tuple(reviewer.lower().split()), "Who is the design reviewer this week?"),
    ]

    turns: list[Turn] = [Turn("system", "You are a coding assistant. Follow all rules and constraints in this session.")]
    positions: dict[str, int] = {}
    filler_i = rng.randrange(len(_FILLER))

    def filler(n: int = 2) -> None:
        nonlocal filler_i
        for _ in range(n):
            turns.append(Turn("user", _FILLER[filler_i % len(_FILLER)]))
            filler_i += 1
            turns.append(Turn("assistant", "Acknowledged. Continuing with the plan."))

    # stale statements early, distinct items in the middle, updates late
    for case in conflicts:
        filler()
        turns.append(Turn("user", case.initial_statement))
        turns.append(Turn("assistant", "Noted."))
    for c in distinct:
        filler()
        positions[c.id] = len(turns)
        turns.append(Turn("user", c.content, canary_id=c.id))
        turns.append(Turn("assistant", "Noted and recorded."))
    for case in conflicts:
        filler()
        positions[case.canary.id] = len(turns)
        turns.append(Turn("user", case.canary.content, canary_id=case.canary.id))
        turns.append(Turn("assistant", "Noted and recorded."))
    filler(3)

    canaries = [case.canary for case in conflicts] + distinct
    meta = {
        "conflicts": [case.canary.id for case in conflicts],
        "initial_statements": {case.canary.id: case.initial_statement for case in conflicts},
        "distinct_pairs": [("d-project-budget", "d-travel-budget"),
                            ("d-launch-deadline", "d-docs-deadline"),
                            ("d-oncall", "d-reviewer")],
    }
    return SeededSession(turns=tuple(turns), canary_positions=positions), canaries, meta
