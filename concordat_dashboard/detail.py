"""Shape one repository's results into its detail page: every rule, with text."""

import dataclasses
import typing as typ

from .marks import label_for

if typ.TYPE_CHECKING:
    from .model import Cell, Finding, RepoResult, RuleInfo, Sweep

GITHUB = "https://github.com"


@dataclasses.dataclass(frozen=True, slots=True)
class Line:
    """One finding, unproven fact or exemption, ready to print."""

    code: str
    location: str
    text: str


@dataclasses.dataclass(frozen=True, slots=True)
class Entry:
    """One rule's section on the detail page."""

    rule_id: str
    name: str
    state: str
    label: str
    breaches: tuple[Line, ...]
    unproven: tuple[Line, ...]
    exemptions: tuple[Line, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class RepoPage:
    """Everything the repository template needs."""

    name: str
    url: str
    commit_url: str
    sha: str
    entries: tuple[Entry, ...]


def _line_of(finding: Finding) -> Line:
    """Print a finding with its file and line.

    Returns
    -------
    Line
        The printable line.
    """
    where = f"{finding.path}:{finding.line}" if finding.line else finding.path
    return Line(finding.code, where, finding.message)


def entry_of(rule: RuleInfo, cell: Cell) -> Entry:
    """Build a rule's section from its cell.

    Parameters
    ----------
    rule
        The rule.
    cell
        The repository's result for it.

    Returns
    -------
    Entry
        The section.
    """
    return Entry(
        rule_id=rule.id,
        name=rule.name,
        state=cell.state.value,
        label=label_for(cell),
        breaches=tuple(_line_of(f) for f in cell.findings),
        unproven=tuple(_line_of(f) for f in cell.unproven),
        exemptions=tuple(Line("", e.path, e.rationale) for e in cell.exemptions),
    )


def page_of(repo: RepoResult, sweep: Sweep) -> RepoPage:
    """Build a repository's detail page view.

    Parameters
    ----------
    repo
        The repository's results.
    sweep
        The sweep, for the rule order and owner.

    Returns
    -------
    RepoPage
        The view model.
    """
    url = f"{GITHUB}/{sweep.owner}/{repo.name}"
    known = repo.sha != "unknown"
    return RepoPage(
        name=repo.name,
        url=url,
        commit_url=f"{url}/commit/{repo.sha}" if known else url,
        sha=repo.sha,
        entries=tuple(entry_of(rule, repo.cells[rule.id]) for rule in sweep.rules),
    )
