"""Shape a `Sweep` into the view model the coupon template draws.

All counting and ordering happens here, so the template only lays things out.
"""

import collections
import dataclasses
import itertools
import typing as typ

from .marks import LABELS, MarkView, mark_for
from .model import RepoResult, RuleInfo, State, Sweep

if typ.TYPE_CHECKING:
    import collections.abc as cabc

STATE_ORDER = (
    State.COMPLIANT,
    State.NONCOMPLIANT,
    State.INDETERMINATE,
    State.EXEMPT,
    State.NOT_APPLICABLE,
)
RESULT_TITLES = (
    "Rules complied with",
    "Rules breached",
    "Rules the sweep could not judge",
    "Rules with an exemption on record",
    "Rules that do not apply",
    "Total findings",
)
RESULT_LABELS = (
    "compliant",
    "non-compliant",
    "indeterminate",
    "exempt",
    "n/a",
    "findings",
)
GITHUB = "https://github.com"
STAKE_TONES = ("", "text-print-red", "text-pencil", "text-pencil", "text-rule")


@dataclasses.dataclass(frozen=True, slots=True)
class ColumnView:
    """One rule column."""

    rule: RuleInfo
    is_first_in_block: bool


@dataclasses.dataclass(frozen=True, slots=True)
class BlockView:
    """A printed block heading over some columns."""

    name: str
    span: int


@dataclasses.dataclass(frozen=True, slots=True)
class RowView:
    """One repository row."""

    number: int
    name: str
    url: str
    sha: str
    marks: tuple[MarkView, ...]
    results: tuple[int, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class FooterCell:
    """One column total."""

    count: int
    is_first_in_block: bool


@dataclasses.dataclass(frozen=True, slots=True)
class FooterLine:
    """One state's totals down the columns."""

    label: str
    cells: tuple[FooterCell, ...]
    total: int


@dataclasses.dataclass(frozen=True, slots=True)
class Stake:
    """One headline figure."""

    label: str
    value: int
    tone: str


@dataclasses.dataclass(frozen=True, slots=True)
class Coupon:
    """Everything the coupon template needs."""

    columns: tuple[ColumnView, ...]
    blocks: tuple[BlockView, ...]
    rows: tuple[RowView, ...]
    footer: tuple[FooterLine, ...]
    stakes: tuple[Stake, ...]
    findings: int
    marks: int


def columns_of(rules: cabc.Sequence[RuleInfo]) -> tuple[ColumnView, ...]:
    """Mark which columns open a block, so the template can draw the heavy rule.

    Parameters
    ----------
    rules
        The rules in column order.

    Returns
    -------
    tuple[ColumnView, ...]
        One view per rule.
    """
    previous = [None, *(r.block for r in rules)]
    return tuple(ColumnView(r, r.block != previous[i]) for i, r in enumerate(rules))


def blocks_of(rules: cabc.Sequence[RuleInfo]) -> tuple[BlockView, ...]:
    """Group consecutive rules into block headings with their widths.

    Parameters
    ----------
    rules
        The rules in column order.

    Returns
    -------
    tuple[BlockView, ...]
        One heading per run of rules sharing a block.
    """
    return tuple(
        BlockView(name, len(list(group)))
        for name, group in itertools.groupby(rules, key=lambda r: r.block)
    )


def row_of(number: int, repo: RepoResult, sweep: Sweep) -> RowView:
    """Build one repository row with its per-row totals.

    Parameters
    ----------
    number
        The one-based row number.
    repo
        The repository's results.
    sweep
        The sweep, for the rule order and owner.

    Returns
    -------
    RowView
        The row.
    """
    cells = [repo.cells[rule.id] for rule in sweep.rules]
    tally = collections.Counter(cell.state for cell in cells)
    findings = sum(len(cell.findings) for cell in cells)
    return RowView(
        number=number,
        name=repo.name,
        url=f"{GITHUB}/{sweep.owner}/{repo.name}",
        sha=repo.sha,
        marks=tuple(
            mark_for(repo.name, rule, cell)
            for rule, cell in zip(sweep.rules, cells, strict=True)
        ),
        results=(*(tally[state] for state in STATE_ORDER), findings),
    )


def footer_of(sweep: Sweep, columns: tuple[ColumnView, ...]) -> tuple[FooterLine, ...]:
    """Total each state down every rule column.

    Parameters
    ----------
    sweep
        The sweep.
    columns
        The column views, for block boundaries.

    Returns
    -------
    tuple[FooterLine, ...]
        One line per state.
    """
    lines = []
    for state in STATE_ORDER:
        counts = [
            sum(1 for r in sweep.repos if r.cells[col.rule.id].state is state)
            for col in columns
        ]
        cells = tuple(
            FooterCell(n, col.is_first_in_block)
            for n, col in zip(counts, columns, strict=True)
        )
        lines.append(FooterLine(LABELS[state].capitalize(), cells, sum(counts)))
    return tuple(lines)


def coupon_of(sweep: Sweep) -> Coupon:
    """Build the whole coupon view from a sweep.

    Parameters
    ----------
    sweep
        The sweep.

    Returns
    -------
    Coupon
        The view model.
    """
    columns = columns_of(sweep.rules)
    rows = tuple(row_of(i, repo, sweep) for i, repo in enumerate(sweep.repos, 1))
    footer = footer_of(sweep, columns)
    stakes = tuple(
        Stake(line.label, line.total, tone)
        for line, tone in zip(footer, STAKE_TONES, strict=True)
    )
    return Coupon(
        columns=columns,
        blocks=blocks_of(sweep.rules),
        rows=rows,
        footer=footer,
        stakes=stakes,
        findings=sum(row.results[-1] for row in rows),
        marks=len(rows) * len(sweep.rules),
    )
