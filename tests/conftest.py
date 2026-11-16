"""Shared fixtures: a small, hand-built sweep that exercises every state."""

import pytest

from concordat_dashboard.model import (
    Cell,
    Excluded,
    Exemption,
    Finding,
    RepoResult,
    RuleInfo,
    State,
    Sweep,
    Trait,
)

RULES = (
    RuleInfo(
        "dependabot-update-shape", "Dependabot update shape", "0.1.0", "UPDATES", None
    ),
    RuleInfo(
        "rust-build-defaults", "Rust build defaults", "0.4.0", "RUST BUILD", Trait.RUST
    ),
    RuleInfo(
        "rust-makefile-baseline",
        "Rust Makefile baseline",
        "0.3.2",
        "RUST BUILD",
        Trait.RUST,
    ),
    RuleInfo(
        "nested-cargo-nextest",
        "Nested cargo nextest",
        "0.1.0",
        "NESTED CARGO",
        Trait.RUST,
    ),
    RuleInfo("yaml-lint-baseline", "YAML lint baseline", "0.1.0", "HOUSE RULES", None),
)
BREACH = Finding("DB-005", ".github/dependabot.yml", 7, "updates[0] has no <groups>")
UNPROVEN = Finding("QG-001", "Makefile", 0, "gate reachability cannot be proven")
EXEMPTION = Exemption("tests/ui.rs", "Compiles one file with rustc.")


@pytest.fixture
def sweep() -> Sweep:
    """Provide two repositories covering every state, plus exclusion counts.

    Returns
    -------
    Sweep
        The sweep.
    """
    rusty = RepoResult(
        "rusty",
        "a" * 40,
        frozenset({Trait.RUST}),
        {
            "dependabot-update-shape": Cell(State.NONCOMPLIANT, (BREACH, BREACH)),
            "rust-build-defaults": Cell(State.COMPLIANT),
            "rust-makefile-baseline": Cell(State.INDETERMINATE, unproven=(UNPROVEN,)),
            "nested-cargo-nextest": Cell(State.EXEMPT, exemptions=(EXEMPTION,)),
            "yaml-lint-baseline": Cell(State.COMPLIANT),
        },
    )
    plain = RepoResult(
        "plain",
        "b" * 40,
        frozenset(),
        {
            "dependabot-update-shape": Cell(State.COMPLIANT),
            "rust-build-defaults": Cell(State.NOT_APPLICABLE),
            "rust-makefile-baseline": Cell(State.NOT_APPLICABLE),
            "nested-cargo-nextest": Cell(State.NOT_APPLICABLE),
            "yaml-lint-baseline": Cell(State.NONCOMPLIANT, (BREACH,)),
        },
    )
    return Sweep(
        owner="leynos",
        generated_at="2026-11-16T04:17:00+00:00",
        concordat_version="0.1.0",
        concordat_commit="e9d254f4439e39c74657037c89bb749ee4372345",
        rules=RULES,
        repos=(plain, rusty),
        excluded=Excluded(forks=21, archived=6, private=11),
    )
