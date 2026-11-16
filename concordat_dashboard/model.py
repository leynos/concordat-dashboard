"""Frozen value types shared by the sweep, the view model and the renderer.

The sweep produces a `Sweep`; everything downstream (JSON, HTML) is derived
from it, so no other module needs to know how a verdict was reached.
"""

import dataclasses
import enum
import typing as typ

if typ.TYPE_CHECKING:
    import collections.abc as cabc


class State(enum.StrEnum):
    """What one repository's mark for one rule means."""

    COMPLIANT = "compliant"
    NONCOMPLIANT = "noncompliant"
    INDETERMINATE = "indeterminate"
    EXEMPT = "exempt"
    NOT_APPLICABLE = "not_applicable"


class Trait(enum.StrEnum):
    """A repository property a rule's applicability can depend on."""

    RUST = "rust"
    PYTHON = "python"
    UV = "uv"


@dataclasses.dataclass(frozen=True, slots=True)
class Finding:
    """One finding reported by a rule, or a reason a rule could not judge."""

    code: str
    path: str
    line: int
    message: str


@dataclasses.dataclass(frozen=True, slots=True)
class Exemption:
    """A shipped exemption on record for a repository."""

    path: str
    rationale: str


@dataclasses.dataclass(frozen=True, slots=True)
class Cell:
    """One mark on the coupon: a repository judged by one rule."""

    state: State
    findings: tuple[Finding, ...] = ()
    exemptions: tuple[Exemption, ...] = ()
    unproven: tuple[Finding, ...] = ()


@dataclasses.dataclass(frozen=True, slots=True)
class RuleInfo:
    """A functioning concordat rule package, as a column of the coupon."""

    id: str
    name: str
    version: str
    block: str
    applies_to: Trait | None


@dataclasses.dataclass(frozen=True, slots=True)
class RepoResult:
    """Every rule's mark for one repository at one commit."""

    name: str
    sha: str
    traits: frozenset[Trait]
    cells: cabc.Mapping[str, Cell]


@dataclasses.dataclass(frozen=True, slots=True)
class Excluded:
    """Counts of repositories left out of the sweep; never names."""

    forks: int
    archived: int
    private: int | None
    empty: int = 0


@dataclasses.dataclass(frozen=True, slots=True)
class Sweep:
    """A complete sweep: the columns, the rows and where they came from."""

    owner: str
    generated_at: str
    concordat_version: str
    concordat_commit: str
    rules: tuple[RuleInfo, ...]
    repos: tuple[RepoResult, ...]
    excluded: Excluded
