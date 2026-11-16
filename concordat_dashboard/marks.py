"""Choose the glyph, wording and link for one mark on the coupon.

A tick is deliberately quiet and a cross is never used: on a coupon an X picks
a selection, but to a reader of a compliance table it reads as failure, and the
most common mark must not look like one. Only breaches are loud.
"""

import dataclasses

from .model import Cell, RuleInfo, State

GLYPHS = {
    State.COMPLIANT: "✓",
    State.INDETERMINATE: "?",
    State.EXEMPT: "E",
    State.NOT_APPLICABLE: "",
}
LABELS = {
    State.COMPLIANT: "compliant",
    State.NONCOMPLIANT: "non-compliant",
    State.INDETERMINATE: "indeterminate",
    State.EXEMPT: "exempt",
    State.NOT_APPLICABLE: "not applicable",
}
LINKED = frozenset({State.NONCOMPLIANT, State.INDETERMINATE, State.EXEMPT})
TITLE_DETAIL_LIMIT = 200


@dataclasses.dataclass(frozen=True, slots=True)
class MarkView:
    """One cell as the template draws it."""

    state: str
    glyph: str
    label: str
    title: str
    href: str | None


def glyph_for(cell: Cell) -> str:
    """Return the visible glyph: the finding count for a breach, else a symbol.

    Parameters
    ----------
    cell
        The cell to draw.

    Returns
    -------
    str
        The text inside the cell.

    Examples
    --------
    >>> from .model import Cell, State
    >>> glyph_for(Cell(State.COMPLIANT))
    '✓'
    """
    if cell.state is State.NONCOMPLIANT:
        return str(len(cell.findings))
    return GLYPHS[cell.state]


def label_for(cell: Cell) -> str:
    """Return the words a screen reader hears for a cell.

    Parameters
    ----------
    cell
        The cell to describe.

    Returns
    -------
    str
        For example "non-compliant, 3 findings".
    """
    label = LABELS[cell.state]
    if cell.state is State.NONCOMPLIANT:
        count = len(cell.findings)
        return f"{label}, {count} finding{'s' if count != 1 else ''}"
    return label


def _detail(cell: Cell) -> str:
    """Return the first line of finding text to put in a tooltip.

    Returns
    -------
    str
        The text, truncated; empty when the cell has none.
    """
    first = (cell.findings or cell.unproven or ())[:1]
    if first:
        return first[0].message[:TITLE_DETAIL_LIMIT]
    if cell.exemptions:
        return cell.exemptions[0].rationale[:TITLE_DETAIL_LIMIT]
    return ""


def mark_for(repo: str, rule: RuleInfo, cell: Cell) -> MarkView:
    """Build the view of one cell, with a tooltip and a link to its finding text.

    Parameters
    ----------
    repo
        The repository name.
    rule
        The rule judged.
    cell
        The result.

    Returns
    -------
    MarkView
        What the template needs to draw the cell.
    """
    label = label_for(cell)
    detail = _detail(cell)
    title = f"{repo} / {rule.id}: {label}" + (f". {detail}" if detail else "")
    href = f"repos/{repo}.html#{rule.id}" if cell.state in LINKED else None
    return MarkView(cell.state.value, glyph_for(cell), label, title, href)
