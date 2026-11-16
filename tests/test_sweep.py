"""One repository is fetched, judged by every rule, and marked."""

import typing as typ

import pytest

from concordat_dashboard import sweep as sweep_module
from concordat_dashboard.classify import RawFinding
from concordat_dashboard.model import Exemption, RuleInfo, State, Trait
from concordat_dashboard.process import git, git_in
from concordat_dashboard.sweep import Locations, SweepConfig, sweep_repository

if typ.TYPE_CHECKING:
    import pathlib

    from concordat_dashboard.sweep import ExemptionIndex

RULES = (
    RuleInfo("always-red", "Always red", "1", "A", None),
    RuleInfo("rusty-only", "Rusty only", "1", "A", Trait.RUST),
    RuleInfo("exempted", "Exempted", "1", "A", None),
)
AUTHOR = ("-c", "user.name=t", "-c", "user.email=t@example.invalid")


class FakeRunner:
    """Stands in for concordat: one rule always breaches, the rest are clean."""

    def run(self, rule_id: str, _tree: pathlib.Path) -> tuple[RawFinding, ...]:
        """Report a breach for `always-red` only.

        Returns
        -------
        tuple[RawFinding, ...]
            The findings.
        """
        if rule_id == "always-red":
            return (RawFinding("R-1", "f", 1, "red", is_indeterminate=False),)
        return ()


def _make_clone(root: pathlib.Path, name: str) -> None:
    """Create `root/name`, a clone of a one-commit upstream holding a .rs file."""
    upstream = root / "upstream" / name
    upstream.mkdir(parents=True)
    git_in(upstream, "init", "--quiet", "--initial-branch", "main")
    (upstream / "lib.rs").write_text("", "utf-8")
    git_in(upstream, "add", ".")
    git_in(upstream, *AUTHOR, "commit", "--quiet", "-m", "first")
    git("clone", "--quiet", str(upstream), str(root / name))


def _config(root: pathlib.Path) -> SweepConfig:
    """Build a config sweeping local clones under *root*.

    Returns
    -------
    SweepConfig
        The config.
    """
    exemptions: ExemptionIndex = {
        "always-red": {},
        "rusty-only": {},
        "exempted": {"leynos/demo": (Exemption("p", "why"),)},
    }
    locations = Locations(root / "work", root / "pins", root)
    return SweepConfig("leynos", RULES, exemptions, locations)


@pytest.fixture(autouse=True)
def fake_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the concordat runner so no rule package or network is needed."""
    monkeypatch.setattr(sweep_module, "_runner", lambda _pins: FakeRunner())


def test_repository_is_marked_per_rule(tmp_path: pathlib.Path) -> None:
    """Breach, applicable-and-clean, and exempt each get their own state."""
    _make_clone(tmp_path, "demo")
    result = sweep_repository("demo", _config(tmp_path))
    states = {rule_id: cell.state for rule_id, cell in result.cells.items()}
    expected = {
        "always-red": State.NONCOMPLIANT,
        "rusty-only": State.COMPLIANT,
        "exempted": State.EXEMPT,
    }
    assert states == expected, "each rule gets its own state"
    assert result.traits == {Trait.RUST}, "the .rs file makes it a Rust repository"
    assert len(result.sha) == 40, "the swept commit is recorded"


def test_unfetchable_repository_is_all_indeterminate_not_a_crash(
    tmp_path: pathlib.Path,
) -> None:
    """One missing clone must not fail the whole sweep."""
    result = sweep_repository("ghost", _config(tmp_path))
    states = {c.state for c in result.cells.values()}
    message = result.cells["always-red"].unproven[0].message
    assert result.sha == "unknown", "no commit was swept"
    assert states == {State.INDETERMINATE}, "every cell is indeterminate"
    assert "checkout failed" in message, "the reason is kept"


def test_checkouts_are_removed_unless_kept(tmp_path: pathlib.Path) -> None:
    """The work directory is empty after a sweep, so a run does not fill the disk."""
    _make_clone(tmp_path, "demo")
    sweep_repository("demo", _config(tmp_path))
    assert not list((tmp_path / "work").iterdir()), "checkouts must be removed"
