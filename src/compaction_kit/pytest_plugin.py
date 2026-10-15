"""Pytest plugin for the compaction conformance kit.

Registered through the `pytest11` entry point, so installing the
package is enough. Define your compactor once, in `conftest.py`:

    import pytest
    from my_compactor import MyCompactor

    @pytest.fixture
    def compactor():
        return MyCompactor()

Then gate it in a test, with the seeded suite by default:

    from compaction_kit.testing import assert_no_flags

    @pytest.mark.compaction(rounds=5, budget_fraction=0.20)
    def test_compaction_gate(compaction_report):
        assert_no_flags(compaction_report)

The marker accepts `rounds` and `budget_fraction` keyword arguments.
Without the marker, `compaction_report` runs 5 rounds with no budget
check. Your `compactor` fixture overrides the placeholder below;
tests that request it without defining one fail with instructions
rather than silently passing.
"""

from __future__ import annotations

import pytest

from .canaries import seeded_canaries as _seeded_canaries
from .session import build_seeded_session as _build_seeded_session
from .testing import check_compactor


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "compaction(rounds=5, budget_fraction=None): run the compactor "
        "fixture through the compaction conformance kit",
    )


@pytest.fixture
def compactor():
    pytest.fail(
        "no `compactor` fixture defined: add one to your conftest.py "
        "returning your compactor instance, e.g.\n\n"
        "    @pytest.fixture\n"
        "    def compactor():\n"
        "        return MyCompactor()\n",
        pytrace=False,
    )


@pytest.fixture
def seeded_session():
    return _build_seeded_session()


@pytest.fixture
def seeded_canaries():
    return _seeded_canaries()


@pytest.fixture
def compaction_report(request, compactor):
    """Conformance report for the `compactor` fixture.

    Honors `@pytest.mark.compaction(rounds=..., budget_fraction=...)`.
    """
    marker = request.node.get_closest_marker("compaction")
    kwargs = marker.kwargs if marker is not None else {}
    return check_compactor(
        compactor,
        rounds=kwargs.get("rounds", 5),
        budget_fraction=kwargs.get("budget_fraction"),
    )
