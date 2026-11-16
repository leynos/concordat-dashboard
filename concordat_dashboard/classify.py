"""Turn a rule's raw findings into the mark shown on the coupon.

Concordat's own verdict has three values. The coupon has five, and it also
refuses to print a red mark for something nobody proved: a finding that says
the reader "cannot prove" a fact is shown as indeterminate, whatever severity
the rule gave it.
"""

import dataclasses
import typing as typ

from .model import Cell, Exemption, Finding, RuleInfo, State, Trait

# Phrases a rule uses when it failed to establish a fact rather than found a
# defect. Each is a reader limit, so the mark must not read as a breach.
UNPROVEN_MARKERS: typ.Final = (
    "cannot be proven",
    "unresolved Make variables",
    "cannot read",
    "no recognized runner platform",
)


@dataclasses.dataclass(frozen=True, slots=True)
class RawFinding:
    """A finding as the rule runner reported it."""

    code: str
    path: str
    line: int
    message: str
    is_indeterminate: bool


def is_unproven(raw: RawFinding) -> bool:
    """Report whether a finding records missing evidence, not a defect.

    Parameters
    ----------
    raw
        The finding as the rule runner reported it.

    Returns
    -------
    bool
        True when concordat marked it indeterminate or its message names a
        reader limit.

    Examples
    --------
    >>> raw = RawFinding("YL-001", "Makefile", 0, "cannot be proven", False)
    >>> is_unproven(raw)
    True
    """
    return raw.is_indeterminate or any(m in raw.message for m in UNPROVEN_MARKERS)


def _as_finding(raw: RawFinding) -> Finding:
    """Drop the runner-only flag from a raw finding.

    Returns
    -------
    Finding
        The finding as the coupon stores it.
    """
    return Finding(raw.code, raw.path, raw.line, raw.message)


def _lacks_trait(rule: RuleInfo, traits: frozenset[Trait]) -> bool:
    """Report whether a rule is about something this repository does not have.

    Returns
    -------
    bool
        True when the rule needs a trait the repository lacks.
    """
    return rule.applies_to is not None and rule.applies_to not in traits


def derive_cell(
    rule: RuleInfo,
    raw: tuple[RawFinding, ...],
    context: tuple[frozenset[Trait], tuple[Exemption, ...]],
) -> Cell:
    """Decide the coupon mark for one repository and one rule.

    A real finding always wins, then missing evidence; only a clean verdict can
    read as exempt or not applicable.

    Parameters
    ----------
    rule
        The rule that ran.
    raw
        Everything the rule reported; empty when it was clean.
    context
        The repository's traits and the exemptions on record for this rule.

    Returns
    -------
    Cell
        The state and the finding text behind it.

    Examples
    --------
    >>> rule = RuleInfo("r", "R", "1", "B", None)
    >>> derive_cell(rule, (), (frozenset(), ())).state
    <State.COMPLIANT: 'compliant'>
    """
    traits, exemptions = context
    proven = tuple(_as_finding(r) for r in raw if not is_unproven(r))
    unproven = tuple(_as_finding(r) for r in raw if is_unproven(r))
    if proven:
        return Cell(State.NONCOMPLIANT, proven, exemptions, unproven)
    if unproven:
        return Cell(State.INDETERMINATE, (), exemptions, unproven)
    if exemptions:
        return Cell(State.EXEMPT, exemptions=exemptions)
    if _lacks_trait(rule, traits):
        return Cell(State.NOT_APPLICABLE)
    return Cell(State.COMPLIANT)
