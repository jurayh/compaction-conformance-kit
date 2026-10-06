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

    p_region = f"eu-north-{rng.randrange(1, 6)}"
    b_region = f"us-west-{rng.randrange(1, 6)}"
    prod_db_version = rng.choice([14, 15, 16])
    staging_db_version = rng.choice([7, 8, 9])
    distinct: list[Canary] = [
        Canary("d-prod-db", CanaryType.FACT,
               f"FACT: The production database is Postgres {prod_db_version} running in {p_region}.",
               (f"postgres {prod_db_version}", p_region, "production database"), "What database and region does production use?"),
        Canary("d-staging-db", CanaryType.FACT,
               f"FACT: The staging database is MySQL {staging_db_version} running in {b_region}.",
               (f"mysql {staging_db_version}", b_region, "staging database"), "What database and region does staging use?"),
        Canary("d-primary-region", CanaryType.FACT,
               f"FACT: The primary deployment region is {p_region}.",
               (p_region, "primary deployment region"), "What is the primary deployment region?"),
        Canary("d-backup-region", CanaryType.FACT,
               f"FACT: The backup deployment region is {b_region}.",
               (b_region, "backup deployment region"), "What is the backup deployment region?"),
        Canary("d-unit-tests", CanaryType.HARD_CONSTRAINT,
               "HARD CONSTRAINT: Run unit tests with pytest before pushing.",
               ("pytest", "unit tests"), "How must unit tests be run before pushing?"),
        Canary("d-integration-tests", CanaryType.HARD_CONSTRAINT,
               "HARD CONSTRAINT: Run integration tests with make test-integration before release.",
               ("make test-integration", "integration tests"), "How must integration tests be run before release?"),
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
        "distinct_pairs": [("d-prod-db", "d-staging-db"),
                            ("d-primary-region", "d-backup-region"),
                            ("d-unit-tests", "d-integration-tests")],
    }
    return SeededSession(turns=tuple(turns), canary_positions=positions), canaries, meta


def build_semantic_heldout_session(seed: int) -> tuple[SeededSession, list[Canary], dict]:
    """Held-out semantic session with new templates and non-overlapping subjects.

    The conflict subjects deliberately do not reuse the distinct-pair
    subjects: spending conflicts govern a trip, while distinct spending
    items govern a project and a conference; deadline conflicts govern a
    release, while distinct deadline items govern launch and docs.
    """
    rng = random.Random(20_000 + seed)
    trip_old = rng.choice([650, 700, 750])
    trip_new_words = _HUNDREDS[rng.choice([4, 5, 6])]
    code_old, code_new = f"{_word(rng, 5).lower()}-{rng.randrange(10,99)}", f"{_word(rng, 5).lower()}-{rng.randrange(10,99)}"
    label_old, label_new = f"{_word(rng)}-{rng.randrange(100,999)}", f"{_word(rng)}-{rng.randrange(100,999)}"
    support_old, support_new = _name(rng), _name(rng)
    branch_old = f"feature/{_word(rng, 5).lower()}-{rng.randrange(10,99)}"
    branch_new = f"feature/{_word(rng, 5).lower()}-{rng.randrange(10,99)}"
    release_old = f"2027-{rng.randrange(1,13):02d}-{rng.randrange(1,29):02d}"
    rel_month, rel_day = rng.choice(_MONTHS), rng.randrange(1, 29)

    conflicts: list[SemanticCase] = [
        SemanticCase(
            Canary("h-spending", CanaryType.HARD_CONSTRAINT,
                   f"New ceiling for trip costs: keep them below {trip_new_words} dollars.",
                   (trip_new_words, "trip costs"), "What is the current trip spending ceiling?"),
            f"HARD CONSTRAINT: Field-trip expenses must stay at or below ${trip_old}."),
        SemanticCase(
            Canary("h-release", CanaryType.FACT,
                   f"Release timing has changed: we now ship on {rel_month} {rel_day}.",
                   (f"{rel_month} {rel_day}".lower(),), "When do we now ship?"),
            f"FACT: The release target date is {release_old}."),
        SemanticCase(
            Canary("h-codename", CanaryType.FACT,
                   f"The internal label for the effort has changed to {label_new}.",
                   (label_new.lower(),), "What is the internal label for the effort now?"),
            f"FACT: Internally, this effort is designated {label_old}."),
        SemanticCase(
            Canary("h-timezone", CanaryType.HARD_CONSTRAINT,
                   "For status reports, show clocks in Pacific Time.",
                   ("pacific",), "How should clocks be shown in status reports now?"),
            "HARD CONSTRAINT: Put every timestamp in UTC."),
        SemanticCase(
            Canary("h-support", CanaryType.FACT,
                   f"Support duty now belongs to {support_new}.",
                   tuple(support_new.lower().split()), "Who has support duty now?"),
            f"FACT: {support_old} is handling support escalation this week."),
        SemanticCase(
            Canary("h-branch", CanaryType.GOAL_STATE,
                   f"We switched active development to branch {branch_new}; next step is regression checks.",
                   (branch_new,), "What branch is active development on now?"),
            f"GOAL STATE: Development is parked on branch {branch_old}."),
        SemanticCase(
            Canary("h-style", CanaryType.USER_PREFERENCE,
                   "Please make responses light and playful, and stick to metric measurements.",
                   ("playful", "metric measurements"), "What response style is wanted now?"),
            "USER PREFERENCE: Keep replies terse and use imperial measurements."),
        SemanticCase(
            Canary("h-code", CanaryType.SAFETY_RULE,
                   f"Access-code rotation is done: never reveal {code_new}; the previous code no longer works.",
                   (code_new,), "What access code must never be revealed now?"),
            f"SAFETY RULE: The maintenance access code is {code_old} and must never be shared."),
    ]
    stale_values = {
        "h-spending": (f"${trip_old}",),
        "h-release": (release_old,),
        "h-codename": (label_old.lower(),),
        "h-timezone": ("utc",),
        "h-support": tuple(support_old.lower().split()),
        "h-branch": (branch_old,),
        "h-style": ("terse", "imperial"),
        "h-code": (code_old,),
    }
    for case in conflicts:
        object.__setattr__(case.canary, "superseded_tokens", stale_values[case.canary.id])

    p_budget = rng.choice([500, 550, 600])
    c_budget = rng.choice([250, 300, 350])
    launch_d = f"2027-{rng.randrange(1,13):02d}-{rng.randrange(1,29):02d}"
    docs_d = f"2027-{rng.randrange(1,13):02d}-{rng.randrange(1,29):02d}"
    approver, reviewer = _name(rng), _name(rng)
    distinct: list[Canary] = [
        Canary("x-project-spending", CanaryType.HARD_CONSTRAINT,
               f"HARD CONSTRAINT: Project spending ceiling is ${p_budget}.",
               (f"${p_budget}", "project spending"), "What is the project spending ceiling?"),
        Canary("x-conference-spending", CanaryType.HARD_CONSTRAINT,
               f"HARD CONSTRAINT: Conference spending ceiling is ${c_budget}.",
               (f"${c_budget}", "conference spending"), "What is the conference spending ceiling?"),
        Canary("x-launch-date", CanaryType.FACT,
               f"FACT: Product launch is scheduled for {launch_d}.",
               (launch_d, "product launch"), "When is the product launch scheduled?"),
        Canary("x-docs-date", CanaryType.FACT,
               f"FACT: Documentation freeze lands on {docs_d}.",
               (docs_d, "documentation freeze"), "When does the documentation freeze land?"),
        Canary("x-release-approver", CanaryType.FACT,
               f"FACT: {approver} is the release approver this week.",
               tuple(approver.lower().split()), "Who is the release approver this week?"),
        Canary("x-design-reviewer", CanaryType.FACT,
               f"FACT: {reviewer} is the design reviewer this week.",
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
        "distinct_pairs": [("x-project-spending", "x-conference-spending"),
                            ("x-launch-date", "x-docs-date"),
                            ("x-release-approver", "x-design-reviewer")],
    }
    return SeededSession(turns=tuple(turns), canary_positions=positions), canaries, meta
