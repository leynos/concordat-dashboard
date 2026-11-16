"""The mark for a cell follows a strict precedence: breach, unproven, exempt, n/a."""

import pytest

from concordat_dashboard.classify import RawFinding, derive_cell, is_unproven
from concordat_dashboard.model import Exemption, RuleInfo, State, Trait

RUST_RULE = RuleInfo("r", "R", "1", "B", Trait.RUST)
ANY_RULE = RuleInfo("a", "A", "1", "B", None)
EXEMPTION = Exemption("x.rs", "because")
BREACH = RawFinding("X-1", "f", 1, "a plain defect", is_indeterminate=False)


def test_clean_rule_on_matching_repository_is_compliant() -> None:
    """No findings, trait present: compliant."""
    cell = derive_cell(RUST_RULE, (), (frozenset({Trait.RUST}), ()))
    assert cell.state is State.COMPLIANT, "a clean Rust repository must be compliant"


def test_clean_rule_without_its_trait_is_not_applicable() -> None:
    """No findings and no Rust: the rule is about something absent."""
    cell = derive_cell(RUST_RULE, (), (frozenset(), ()))
    assert cell.state is State.NOT_APPLICABLE, "no Rust trait must read not applicable"


def test_rule_with_no_trait_requirement_is_never_not_applicable() -> None:
    """A rule about any repository reads compliant even when traits are empty."""
    cell = derive_cell(ANY_RULE, (), (frozenset(), ()))
    assert cell.state is State.COMPLIANT, "an any-repository rule must be compliant"


def test_exemption_on_record_reads_exempt() -> None:
    """A clean verdict with an exemption on record is exempt, not compliant."""
    cell = derive_cell(ANY_RULE, (), (frozenset(), (EXEMPTION,)))
    assert cell.state is State.EXEMPT, "a clean verdict with an exemption is exempt"
    assert cell.exemptions == (EXEMPTION,), "the exemption must be kept for display"


def test_finding_wins_over_missing_trait() -> None:
    """A breach is shown even on a repository the table calls not applicable."""
    cell = derive_cell(RUST_RULE, (BREACH,), (frozenset(), ()))
    assert cell.state is State.NONCOMPLIANT, (
        "a finding must beat the applicability table"
    )
    assert len(cell.findings) == 1, "the finding must be kept"


@pytest.mark.parametrize(
    "message",
    [
        "no recipe provably runs yamllint; unresolved Make variables: HOME",
        "lint reaches an unproven recursive Make invocation; recipes cannot be proven",
        "job x delegates to a reusable workflow this audit cannot read",
    ],
)
def test_reader_limits_are_unproven_not_breaches(message: str) -> None:
    """A finding that says evidence is missing must not print as a breach."""
    raw = RawFinding("YL-001", "Makefile", 0, message, is_indeterminate=False)
    cell = derive_cell(ANY_RULE, (raw,), (frozenset(), ()))
    assert is_unproven(raw), "a reader-limit message is unproven"
    assert cell.state is State.INDETERMINATE, "a reader limit must not be a breach"
    assert cell.unproven[0].message == message, "the reason must be kept"


def test_concordat_indeterminate_flag_is_honoured() -> None:
    """A finding concordat itself marks indeterminate is unproven."""
    raw = RawFinding("EN-001", "t.rs", 3, "cannot tell", is_indeterminate=True)
    cell = derive_cell(ANY_RULE, (raw,), (frozenset(), ()))
    assert cell.state is State.INDETERMINATE, "concordat's own flag must be honoured"


def test_breach_and_unproven_together_keep_both() -> None:
    """A real breach makes the cell non-compliant and keeps the unproven text."""
    unproven = RawFinding("E", "", 0, "cannot be proven", is_indeterminate=False)
    cell = derive_cell(ANY_RULE, (BREACH, unproven), (frozenset(), ()))
    assert cell.state is State.NONCOMPLIANT, "a real breach decides the state"
    assert (len(cell.findings), len(cell.unproven)) == (1, 1), "both lists are kept"


def test_breach_beats_an_exemption_on_record() -> None:
    """An exemption never hides a finding the rule still reports."""
    cell = derive_cell(ANY_RULE, (BREACH,), (frozenset(), (EXEMPTION,)))
    assert cell.state is State.NONCOMPLIANT, "the breach decides the state"
    assert cell.exemptions == (EXEMPTION,), "the exemption is shown beside it"
