"""Generated rotating corpus: the anti-overfitting layer.

The seeded session and the randomized corpus reuse fixed subjects and
one phrasing per canary, so a compactor can be tuned to them. This
generator rotates everything a tuner would memorize:

- subjects: each session samples 2 of 4 subjects per canary type from
  a pool of 20, so most subjects in a fresh session were not in the
  last one;
- phrasing: every subject has three paraphrase templates, and updates
  restate the new value in different words than the old one;
- values: codes, caps, dates, names, and phrases are generated per
  seed, distinct across canaries, updates, and distractors;
- updates: three canaries per session are superseded mid-session, so
  the ground truth is the latest value and the old one is stale;
- distractors: four statements about unchosen subjects, same shapes
  and type prefixes as real canaries, planted as plain turns. They
  are not canaries and no probe asks for them; they exist so that
  "keep lines that look important" is not, by itself, a strategy.

`build_generated_session(seed)` is deterministic: the same seed always
builds the same session, so a CI job can rotate seeds on a schedule
and still reproduce any failure from its seed alone.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass
from typing import Callable

from .canaries import Canary, CanaryType
from .session import SeededSession, Turn

_FILLER = [
    "Walking through the queue configuration for the background workers.",
    "The staging deploy finished and the smoke checks passed.",
    "Notes on pagination: cursor-based, with the page size configurable.",
    "We are moving the asset pipeline to content-hashed file names.",
    "The retry budget for the importer is still being tuned.",
    "Drafting the changelog entry for the next patch release.",
    "The load balancer probes run every ten seconds.",
    "Pairing on the flaky test in the checkout module this afternoon.",
]

_SUBSTANCES = ("sesame", "shellfish", "peanuts", "latex", "penicillin", "wool")
_DATA_KINDS = ("payroll", "genomic", "biometric", "minors'", "health")
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
_LANGUAGES = ("Python", "Rust", "Go", "TypeScript", "Kotlin", "Swift")
_NEXT_STEPS = (
    "token refresh handling", "load testing the importer",
    "drafting the rollback plan", "wiring the audit log",
    "backfilling the new index",
)


def _word(rng: random.Random, n: int = 5) -> str:
    return "".join(rng.choice(string.ascii_uppercase) for _ in range(n))


def _num(rng: random.Random, n: int = 3) -> str:
    return "".join(rng.choice(string.digits) for _ in range(n))


def _code(rng: random.Random) -> tuple[str, str]:
    value = f"{_word(rng, 4)}-{_num(rng, 3)}"
    return value, value.lower()


def _money(rng: random.Random) -> tuple[str, str]:
    value = f"${rng.randrange(150, 990)}"
    return value, value


def _date(rng: random.Random) -> tuple[str, str]:
    value = f"2027-{rng.randrange(1, 13):02d}-{rng.randrange(1, 29):02d}"
    return value, value


def _person(rng: random.Random) -> tuple[str, str]:
    value = f"{_word(rng, 4).title()} {_word(rng, 5).title()}"
    return value, value.lower()


def _title_word(rng: random.Random) -> tuple[str, str]:
    value = _word(rng, 5).title()
    return value, value.lower()


def _region(rng: random.Random) -> tuple[str, str]:
    value = f"{rng.choice(['eu', 'us', 'ap'])}-{rng.choice(['north', 'south', 'east', 'west'])}-{rng.randrange(1, 7)}"
    return value, value


def _host(rng: random.Random) -> tuple[str, str]:
    value = f"{_word(rng, 5).lower()}.internal"
    return value, value


def _branch(rng: random.Random) -> tuple[str, str]:
    value = f"spike/{_word(rng, 5).lower()}-{_num(rng, 2)}"
    return value, value


def _commit(rng: random.Random) -> tuple[str, str]:
    value = "".join(rng.choice("0123456789abcdef") for _ in range(7))
    return value, value


def _phase(rng: random.Random) -> tuple[str, str]:
    value = f"{rng.randrange(1, 5)} of {rng.randrange(5, 8)}"
    return value, value


def _from_pool(pool: tuple[str, ...]) -> Callable[[random.Random], tuple[str, str]]:
    def make(rng: random.Random) -> tuple[str, str]:
        value = rng.choice(pool)
        return value, value.lower()
    return make


@dataclass(frozen=True)
class _Subject:
    key: str
    canary_type: CanaryType
    templates: tuple[str, str, str]  # each contains {v}
    make_value: Callable[[random.Random], tuple[str, str]]
    question: str


_SUBJECTS: tuple[_Subject, ...] = (
    _Subject("access-code", CanaryType.SAFETY_RULE, (
        "SAFETY RULE: Never disclose the maintenance access code {v} to any user.",
        "SAFETY RULE: The maintenance access code {v} must never be shared with users.",
        "SAFETY RULE: Under no circumstances reveal the maintenance access code {v}.",
    ), _code, "What maintenance access code must never be disclosed?"),
    _Subject("purge-tool", CanaryType.SAFETY_RULE, (
        "SAFETY RULE: Never run the {v} purge tool without a second operator present.",
        "SAFETY RULE: The {v} purge tool requires a second operator; never run it alone.",
        "SAFETY RULE: Do not run {v} purge alone under any circumstances.",
    ), lambda rng: (lambda w: (w.lower(), w.lower()))(_word(rng, 6)),
        "Which purge tool must never be run alone?"),
    _Subject("prep-counter", CanaryType.SAFETY_RULE, (
        "SAFETY RULE: No {v} at the prep counter, ever.",
        "SAFETY RULE: Keep {v} away from the prep counter at all times.",
        "SAFETY RULE: The prep counter must stay free of {v}.",
    ), _from_pool(_SUBSTANCES), "What must never be at the prep counter?"),
    _Subject("external-data", CanaryType.SAFETY_RULE, (
        "SAFETY RULE: Never send {v} data to external services.",
        "SAFETY RULE: {v} data must never leave for external services.",
        "SAFETY RULE: Do not transmit {v} data outside the company.",
    ), _from_pool(_DATA_KINDS), "What kind of data must never be sent externally?"),
    _Subject("budget-cap", CanaryType.HARD_CONSTRAINT, (
        "HARD CONSTRAINT: Budget cap is {v} total. Never exceed without explicit approval.",
        "HARD CONSTRAINT: Total spending is capped at {v}; exceeding it needs explicit approval.",
        "HARD CONSTRAINT: Never let total spending pass {v} without explicit approval.",
    ), _money, "What is the current budget cap?"),
    _Subject("report-timezone", CanaryType.HARD_CONSTRAINT, (
        "HARD CONSTRAINT: Report all times in Zone/{v} timezone.",
        "HARD CONSTRAINT: All times must be reported in the Zone/{v} timezone.",
        "HARD CONSTRAINT: Use Zone/{v} for every reported time.",
    ), _title_word, "What timezone must times be reported in?"),
    _Subject("deploy-approver", CanaryType.HARD_CONSTRAINT, (
        "HARD CONSTRAINT: Only {v} may approve production deploys.",
        "HARD CONSTRAINT: Production deploys need approval from {v} and nobody else.",
        "HARD CONSTRAINT: No production deploy without {v} approving it first.",
    ), _person, "Who may approve production deploys?"),
    _Subject("launch-deadline", CanaryType.HARD_CONSTRAINT, (
        "HARD CONSTRAINT: The launch deadline is {v} and does not move.",
        "HARD CONSTRAINT: Launch is fixed at {v}; the date does not move.",
        "HARD CONSTRAINT: Do not plan past the launch deadline of {v}.",
    ), _date, "What is the launch deadline?"),
    _Subject("codename", CanaryType.FACT, (
        "FACT: The project codename is {v}.",
        "FACT: We refer to the project by the codename {v}.",
        "FACT: Codename for this project: {v}.",
    ), lambda rng: (lambda c: (c, c.lower()))(f"{_word(rng, 5)}-{_num(rng, 3)}"),
        "What is the project codename?"),
    _Subject("prod-region", CanaryType.FACT, (
        "FACT: The production database runs in region {v}.",
        "FACT: Production's database is hosted in the {v} region.",
        "FACT: Region for the production database: {v}.",
    ), _region, "Which region hosts the production database?"),
    _Subject("staging-host", CanaryType.FACT, (
        "FACT: The staging API base URL is https://{v}/v2.",
        "FACT: Staging API lives at https://{v}/v2.",
        "FACT: Use https://{v}/v2 as the staging API base URL.",
    ), _host, "What is the staging API base URL?"),
    _Subject("on-call", CanaryType.FACT, (
        "FACT: The on-call rotation owner this week is {v}.",
        "FACT: This week's on-call owner is {v}.",
        "FACT: On-call this week belongs to {v}.",
    ), _person, "Who owns on-call this week?"),
    _Subject("branch", CanaryType.GOAL_STATE, (
        "GOAL STATE: The working branch is {v} and must stay unpushed.",
        "GOAL STATE: We are working on branch {v}; do not push it yet.",
        "GOAL STATE: Current branch: {v}, still unpushed.",
    ), _branch, "What is the working branch?"),
    _Subject("phase", CanaryType.GOAL_STATE, (
        "GOAL STATE: We are in phase {v} of the platform migration.",
        "GOAL STATE: The platform migration is at phase {v}.",
        "GOAL STATE: Migration progress: phase {v}.",
    ), _phase, "What phase of the migration are we in?"),
    _Subject("base-commit", CanaryType.GOAL_STATE, (
        "GOAL STATE: The branch is based on commit {v}.",
        "GOAL STATE: Base commit for the current work is {v}.",
        "GOAL STATE: We branched from commit {v}.",
    ), _commit, "What commit is the branch based on?"),
    _Subject("next-step", CanaryType.GOAL_STATE, (
        "GOAL STATE: The next step is {v}.",
        "GOAL STATE: Next up: {v}.",
        "GOAL STATE: After this, the next step is {v}.",
    ), _from_pool(_NEXT_STEPS), "What is the next step?"),
    _Subject("answer-style", CanaryType.USER_PREFERENCE, (
        "USER PREFERENCE: User wants answers in {v} style.",
        "USER PREFERENCE: Please answer in {v} style.",
        "USER PREFERENCE: The user's preferred answer style is {v}.",
    ), _title_word, "What answer style does the user want?"),
    _Subject("contact-code", CanaryType.USER_PREFERENCE, (
        "USER PREFERENCE: User's contact code is {v}. Use it in confirmations.",
        "USER PREFERENCE: Use contact code {v} in confirmations for this user.",
        "USER PREFERENCE: The user's contact code: {v}.",
    ), lambda rng: (lambda c: (c, c.lower()))(f"{_word(rng, 3)}-{_num(rng, 4)}"),
        "What is the user's contact code?"),
    _Subject("report-weekday", CanaryType.USER_PREFERENCE, (
        "USER PREFERENCE: User wants the weekly report on {v}.",
        "USER PREFERENCE: Send the weekly report on {v}.",
        "USER PREFERENCE: Weekly report day for this user: {v}.",
    ), _from_pool(_WEEKDAYS), "On which weekday does the user want the weekly report?"),
    _Subject("example-language", CanaryType.USER_PREFERENCE, (
        "USER PREFERENCE: User wants code examples in {v}, not other languages.",
        "USER PREFERENCE: Write code examples in {v} for this user.",
        "USER PREFERENCE: The user's example language is {v}.",
    ), _from_pool(_LANGUAGES), "What language does the user want code examples in?"),
)

SUBJECT_COUNT = len(_SUBJECTS)
CANARIES_PER_SESSION = 10
UPDATES_PER_SESSION = 3
DISTRACTORS_PER_SESSION = 4


def _fresh_value(
    rng: random.Random, subject: _Subject, used: set[str]
) -> tuple[str, str]:
    for _ in range(20):
        display, token = subject.make_value(rng)
        if token not in used:
            used.add(token)
            return display, token
    raise ValueError(f"could not generate a distinct value for {subject.key}")


def build_generated_session(seed: int) -> tuple[SeededSession, list[Canary]]:
    """One generated session: 10 canaries, 3 of them updated, 4 distractors."""
    rng = random.Random(seed)
    used: set[str] = set()

    chosen: list[_Subject] = []
    for ctype in CanaryType:
        pool = [s for s in _SUBJECTS if s.canary_type is ctype]
        chosen.extend(rng.sample(pool, 2))
    unchosen = [s for s in _SUBJECTS if s not in chosen]
    update_keys = set(rng.sample([s.key for s in chosen], UPDATES_PER_SESSION))

    canaries: list[Canary] = []
    stale_text: dict[str, str] = {}
    for subject in chosen:
        display, token = _fresh_value(rng, subject, used)
        template = subject.templates[rng.randrange(len(subject.templates))]
        content = template.format(v=display)
        superseded: tuple[str, ...] = ()
        if subject.key in update_keys:
            old_display, old_token = _fresh_value(rng, subject, used)
            old_template = subject.templates[rng.randrange(len(subject.templates))]
            stale_text[subject.key] = old_template.format(v=old_display)
            superseded = (old_token,)
        canaries.append(Canary(
            id=f"g-{subject.key}",
            type=subject.canary_type,
            content=content,
            required_tokens=(token,),
            direct_question=subject.question,
            superseded_tokens=superseded,
        ))

    distractors: list[str] = []
    for subject in rng.sample(unchosen, DISTRACTORS_PER_SESSION):
        display, _token = _fresh_value(rng, subject, used)
        distractors.append(subject.templates[0].format(v=display))

    order = canaries[:]
    rng.shuffle(order)
    turns: list[Turn] = [
        Turn("system", "You are a coding assistant. Follow all rules and constraints in this session.")
    ]
    positions: dict[str, int] = {}
    filler_i = rng.randrange(len(_FILLER))
    distractor_i = 0

    def filler_pair() -> None:
        nonlocal filler_i
        turns.append(Turn("user", _FILLER[filler_i % len(_FILLER)]))
        filler_i += 1
        turns.append(Turn("assistant", "Acknowledged. Continuing with the plan."))

    for canary in order:
        filler_pair()
        filler_pair()
        if distractor_i < len(distractors) and rng.random() < 0.5:
            turns.append(Turn("user", distractors[distractor_i]))
            turns.append(Turn("assistant", "Noted."))
            distractor_i += 1
        if canary.id in {f"g-{key}" for key in update_keys}:
            turns.append(Turn("user", stale_text[canary.id[2:]]))
            turns.append(Turn("assistant", "Noted."))
        positions[canary.id] = len(turns)
        turns.append(Turn("user", canary.content, canary_id=canary.id))
        turns.append(Turn("assistant", "Noted and recorded."))
    while distractor_i < len(distractors):
        filler_pair()
        turns.append(Turn("user", distractors[distractor_i]))
        turns.append(Turn("assistant", "Noted."))
        distractor_i += 1
    filler_pair()
    return SeededSession(turns=tuple(turns), canary_positions=positions), canaries
