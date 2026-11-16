"""Each mark links, titles and words itself; detail pages cover every rule."""

import typing as typ

from concordat_dashboard.detail import entry_of, page_of
from concordat_dashboard.marks import TITLE_DETAIL_LIMIT, mark_for
from concordat_dashboard.model import Cell, Exemption, Finding, RepoResult, State

if typ.TYPE_CHECKING:
    from concordat_dashboard.model import RuleInfo, Sweep

FINDING = Finding("X-1", "Makefile", 3, "a finding message")


def _rule(sweep: Sweep) -> RuleInfo:
    """Return the sample sweep's first rule.

    Returns
    -------
    RuleInfo
        The rule.
    """
    return sweep.rules[0]


def test_marks_with_text_link_to_their_section(sweep: Sweep) -> None:
    """Breached, indeterminate and exempt marks link; others do not."""
    rule = _rule(sweep)
    linked = {
        State.NONCOMPLIANT: Cell(State.NONCOMPLIANT, (FINDING,)),
        State.INDETERMINATE: Cell(State.INDETERMINATE, unproven=(FINDING,)),
        State.EXEMPT: Cell(State.EXEMPT, exemptions=(Exemption("p", "why"),)),
    }
    for state, cell in linked.items():
        href = mark_for("demo", rule, cell).href
        assert href == f"repos/demo.html#{rule.id}", f"{state} must link"
    for state in (State.COMPLIANT, State.NOT_APPLICABLE):
        assert mark_for("demo", rule, Cell(state)).href is None, f"{state} has no link"


def test_title_carries_repository_rule_state_and_first_finding(sweep: Sweep) -> None:
    """The tooltip is enough to read the first finding without following the link."""
    cell = Cell(State.NONCOMPLIANT, (FINDING,))
    title = mark_for("demo", _rule(sweep), cell).title
    start = "demo / dependabot-update-shape: non-compliant, 1 finding"
    assert title.startswith(start), "the title names the repository, rule and state"
    assert title.endswith("a finding message"), "the first finding follows the state"


def test_long_finding_text_is_truncated_in_the_title(sweep: Sweep) -> None:
    """A tooltip is a glance; the full text is on the detail page."""
    long_finding = Finding("X-1", "f", 1, "w" * (TITLE_DETAIL_LIMIT + 50))
    title = mark_for("d", _rule(sweep), Cell(State.NONCOMPLIANT, (long_finding,))).title
    assert title.endswith("w" * TITLE_DETAIL_LIMIT), "the detail is kept to the limit"
    assert "w" * (TITLE_DETAIL_LIMIT + 1) not in title, "and no longer than that"


def test_title_for_an_exemption_quotes_the_rationale(sweep: Sweep) -> None:
    """An exempt mark's tooltip says why."""
    cell = Cell(State.EXEMPT, exemptions=(Exemption("p", "a fixture crate"),))
    title = mark_for("demo", _rule(sweep), cell).title
    assert title.endswith("a fixture crate"), "the rationale is the detail"


def test_detail_page_has_a_section_per_rule_in_rule_order(sweep: Sweep) -> None:
    """Every rule gets an anchor, so any mark's link has a target."""
    page = page_of(sweep.repos[1], sweep)
    assert [e.rule_id for e in page.entries] == [r.id for r in sweep.rules], "order"
    assert page.commit_url.endswith(f"/commit/{'a' * 40}"), "links to the commit"


def test_detail_page_of_an_unfetched_repository_links_to_the_repository(
    sweep: Sweep,
) -> None:
    """With no commit swept there is no commit URL to offer."""
    repo = RepoResult("ghost", "unknown", frozenset(), sweep.repos[0].cells)
    assert page_of(repo, sweep).commit_url.endswith("/leynos/ghost"), "repository URL"


def test_title_falls_back_to_the_unproven_message_without_findings(
    sweep: Sweep,
) -> None:
    """An indeterminate cell with no finding quotes its unproven message."""
    unproven = Finding("X-2", "Makefile", 0, "cannot be proven")
    cell = Cell(State.INDETERMINATE, unproven=(unproven,))
    title = mark_for("demo", _rule(sweep), cell).title
    assert title.endswith(". cannot be proven"), "the unproven message is the detail"


def test_title_has_no_detail_when_the_cell_has_no_text(sweep: Sweep) -> None:
    """A compliant cell has nothing to quote, so the title ends at its state."""
    title = mark_for("demo", _rule(sweep), Cell(State.COMPLIANT)).title
    assert title == "demo / dependabot-update-shape: compliant", "no trailing detail"


def test_detail_entry_routes_findings_unproven_and_exemptions(sweep: Sweep) -> None:
    """Each kind of cell text lands in its own section of the entry."""
    rule = _rule(sweep)
    unproven = Finding("X-2", "", 0, "cannot be proven")
    cell = Cell(
        State.NONCOMPLIANT,
        (FINDING,),
        (Exemption("crates/x", "a fixture crate"),),
        (unproven,),
    )
    entry = entry_of(rule, cell)
    assert [(b.code, b.location, b.text) for b in entry.breaches] == [
        ("X-1", "Makefile:3", "a finding message")
    ], "a finding with a line shows path:line"
    assert [(u.location, u.text) for u in entry.unproven] == [
        ("", "cannot be proven")
    ], "a finding with no line shows the bare path"
    assert [(e.location, e.text) for e in entry.exemptions] == [
        ("crates/x", "a fixture crate")
    ], "an exemption shows its path and rationale"
