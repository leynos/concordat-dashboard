"""The view model does every count, so the template only lays things out."""

import typing as typ

from concordat_dashboard.marks import glyph_for, label_for
from concordat_dashboard.model import Cell, Finding, State
from concordat_dashboard.view import blocks_of, columns_of, coupon_of

if typ.TYPE_CHECKING:
    from concordat_dashboard.model import Sweep

ONE = Finding("X", "f", 1, "m")


def test_blocks_group_consecutive_rules(sweep: Sweep) -> None:
    """Block headings carry the width of their run."""
    blocks = [(b.name, b.span) for b in blocks_of(sweep.rules)]
    assert blocks[:2] == [("UPDATES", 1), ("RUST BUILD", 2)], "runs share a heading"
    assert sum(span for _, span in blocks) == len(sweep.rules), "spans cover columns"


def test_columns_flag_the_first_of_each_block(sweep: Sweep) -> None:
    """The heavy rule is drawn before each block's first column."""
    flags = [c.is_first_in_block for c in columns_of(sweep.rules)]
    assert flags == [True, True, False, True, True], "block starts are flagged"


def test_row_results_sum_to_the_rule_count(sweep: Sweep) -> None:
    """Every rule falls in exactly one result column; the last is findings."""
    for row in coupon_of(sweep).rows:
        assert sum(row.results[:5]) == len(sweep.rules), f"{row.name} tally is short"


def test_row_results_count_states_and_findings(sweep: Sweep) -> None:
    """Rows are in sweep order; the first row is the plain repository."""
    plain, rusty = coupon_of(sweep).rows
    assert plain.results == (1, 1, 0, 0, 3, 1), "plain repository tally"
    assert rusty.results == (2, 1, 1, 1, 0, 2), "rusty repository tally"


def test_footer_totals_each_state_down_the_columns(sweep: Sweep) -> None:
    """Footer lines follow the state order and add up to the stakes."""
    coupon = coupon_of(sweep)
    assert [line.total for line in coupon.footer] == [3, 2, 1, 1, 3], "footer totals"
    assert [s.value for s in coupon.stakes] == [3, 2, 1, 1, 3], "stakes match footer"
    assert (coupon.findings, coupon.marks) == (3, 10), "headline figures"


def test_breach_glyph_is_its_count_and_compliant_is_not_a_cross() -> None:
    """A tick is quiet; a cross would read as failure."""
    assert glyph_for(Cell(State.NONCOMPLIANT, (ONE, ONE, ONE))) == "3", "count"
    tick = glyph_for(Cell(State.COMPLIANT))
    assert tick == "\N{CHECK MARK}", "compliant is a tick"
    assert "\N{MULTIPLICATION SIGN}" not in tick, "never a cross"


def test_labels_are_words_with_singular_and_plural() -> None:
    """Screen readers hear the state and the count."""
    one = label_for(Cell(State.NONCOMPLIANT, (ONE,)))
    two = label_for(Cell(State.NONCOMPLIANT, (ONE, ONE)))
    assert (one, two) == ("non-compliant, 1 finding", "non-compliant, 2 findings"), (
        "plural follows the count"
    )
    assert label_for(Cell(State.NOT_APPLICABLE)) == "not applicable", "plain words"
