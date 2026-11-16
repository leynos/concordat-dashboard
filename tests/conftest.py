"""Shared fixtures: a hand-built sweep for every state, and tiny git repositories."""

import typing as typ

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
from concordat_dashboard.process import git, git_in

if typ.TYPE_CHECKING:
    import collections.abc as cabc
    import pathlib

AUTHOR = ("-c", "user.name=t", "-c", "user.email=t@example.invalid")
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


@pytest.fixture
def commit_all() -> cabc.Callable[[pathlib.Path, str], None]:
    """Provide a function that commits everything in a repository.

    Returns
    -------
    cabc.Callable[[pathlib.Path, str], None]
        Commits all changes in the given repository with the given message.
    """

    def commit(repo: pathlib.Path, message: str) -> None:
        """Stage and commit every change in *repo*."""
        git_in(repo, "add", ".")
        git_in(repo, *AUTHOR, "commit", "--quiet", "-m", message)

    return commit


@pytest.fixture
def make_clone(
    tmp_path: pathlib.Path,
    commit_all: cabc.Callable[[pathlib.Path, str], None],
) -> cabc.Callable[[str, dict[str, str]], pathlib.Path]:
    """Provide a function that makes `tmp_path/<name>`, a clone of a new upstream.

    Returns
    -------
    cabc.Callable[[str, dict[str, str]], pathlib.Path]
        Takes a name and the files of the single commit; returns the clone.
    """

    def make(name: str, files: dict[str, str]) -> pathlib.Path:
        """Create the upstream with *files*, then clone it.

        Returns
        -------
        pathlib.Path
            The clone, whose `origin/HEAD` is the upstream's branch.
        """
        upstream = tmp_path / "upstream" / name
        upstream.mkdir(parents=True)
        git_in(upstream, "init", "--quiet", "--initial-branch", "main")
        for relative, text in files.items():
            path = upstream / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, "utf-8")
        commit_all(upstream, "first")
        clone = tmp_path / name
        git("clone", "--quiet", str(upstream), str(clone))
        return clone

    return make


@pytest.fixture
def clone(
    make_clone: cabc.Callable[[str, dict[str, str]], pathlib.Path],
) -> pathlib.Path:
    """Provide a clone named `demo` holding a README and a Rust source file.

    Returns
    -------
    pathlib.Path
        The clone, one directory below `tmp_path`.
    """
    return make_clone("demo", {"README.md": "hello\n", "lib.rs": ""})
