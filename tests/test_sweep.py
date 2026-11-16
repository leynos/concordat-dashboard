"""One repository is fetched, judged by every rule, and marked."""

import concurrent.futures as cf
import dataclasses
import pathlib
import typing as typ

import pytest

from concordat_dashboard import sweep as sweep_module
from concordat_dashboard.classify import RawFinding
from concordat_dashboard.model import Excluded, Exemption, RuleInfo, State, Sweep, Trait
from concordat_dashboard.process import CommandFailedError
from concordat_dashboard.render import write_site
from concordat_dashboard.sweep import Locations, SweepConfig, sweep_repository

if typ.TYPE_CHECKING:
    from concordat_dashboard.sweep import ExemptionIndex

RULES = (
    RuleInfo("always-red", "Always red", "1", "A", None),
    RuleInfo("rusty-only", "Rusty only", "1", "A", Trait.RUST),
    RuleInfo("exempted", "Exempted", "1", "A", None),
)


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
    monkeypatch.setattr(sweep_module, "_runner", lambda *_args: FakeRunner())


def test_relative_local_root_is_resolved_before_the_fetch(
    clone: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fetch runs inside the work tree, so a relative path must not leak in."""
    monkeypatch.chdir(clone.parent)
    base = _config(clone.parent)
    locations = dataclasses.replace(base.locations, local_root=pathlib.Path())
    result = sweep_repository("demo", dataclasses.replace(base, locations=locations))
    assert len(result.sha) == 40, "a relative local root must still fetch"


def test_owner_case_does_not_hide_an_exemption(clone: pathlib.Path) -> None:
    """GitHub names are case-insensitive; the exemption must still match."""
    config = dataclasses.replace(_config(clone.parent), owner="Leynos")
    result = sweep_repository("demo", config)
    assert result.cells["exempted"].state is State.EXEMPT, "exemption must match"


def test_unreadable_repository_is_all_indeterminate_not_a_crash(
    clone: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read error in one repository must not stop the estate sweep."""

    class UnreadableRunner:
        """A runner whose rule cannot read the checkout."""

        def run(self, _rule_id: str, _tree: pathlib.Path) -> tuple[RawFinding, ...]:
            """Fail as a permission error would.

            Raises
            ------
            PermissionError
                Always.
            """
            message = "denied"
            raise PermissionError(message)

    monkeypatch.setattr(sweep_module, "_runner", lambda *_args: UnreadableRunner())
    result = sweep_repository("demo", _config(clone.parent))
    message = result.cells["always-red"].unproven[0].message
    assert result.sha == "unknown", "the repository is not swept"
    assert "could not be read (PermissionError)" in message, "the kind is kept"
    assert "denied" not in message, "the exception text is not published"


def test_repository_is_marked_per_rule(clone: pathlib.Path) -> None:
    """Breach, applicable-and-clean, and exempt each get their own state."""
    result = sweep_repository("demo", _config(clone.parent))
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


def test_checkouts_are_removed_unless_kept(clone: pathlib.Path) -> None:
    """The work directory is empty after a sweep, so a run does not fill the disk."""
    root = clone.parent
    sweep_repository("demo", _config(root))
    assert not list((root / "work").iterdir()), "checkouts must be removed"


def test_command_output_never_reaches_the_published_reason(
    clone: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A command's stderr may name a private repository; only its summary is shown."""

    def refuse(*_args: object) -> str:
        """Fail as a git fetch with a revealing stderr would.

        Raises
        ------
        CommandFailedError
            Always.
        """
        full = "git fetch failed (128): repository leynos/a-private-repository gone"
        raise CommandFailedError(full, "git fetch failed (128)")

    monkeypatch.setattr(sweep_module, "checkout_tree", refuse)
    result = sweep_repository("demo", _config(clone.parent))
    message = result.cells["always-red"].unproven[0].message
    assert "git fetch failed (128)" in message, "the summary is published"
    assert "a-private-repository" not in message, "command output must not be"


def test_breach_beats_an_exemption_on_record(clone: pathlib.Path) -> None:
    """A real finding is shown even when an exemption is on record for the rule."""
    base = _config(clone.parent)
    exemption = {"leynos/demo": (Exemption("p", "why"),)}
    config = dataclasses.replace(
        base, exemptions={**base.exemptions, "always-red": exemption}
    )
    cell = sweep_repository("demo", config).cells["always-red"]
    assert cell.state is State.NONCOMPLIANT, "a breach must not be hidden"
    assert cell.exemptions, "the exemption is still shown beside it"


def test_collect_returns_results_in_name_order_and_logs_public_names(
    clone: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Orchestration reports progress per repository and sorts the rows."""
    config = _config(clone.parent)
    with caplog.at_level("INFO"), cf.ThreadPoolExecutor(max_workers=2) as pool:
        results = sweep_module.collect(pool, ("zzz-ghost", "demo"), config)
    assert [r.name for r in results] == ["demo", "zzz-ghost"], "name order"
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "swept 2/2" in logged, "progress is logged"
    assert "demo" in logged, "public names are logged"


def test_swept_repository_renders_with_its_finding_text(
    clone: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """From a swept repository to a detail page: the path the generator takes."""
    config = _config(clone.parent)
    repo = sweep_repository("demo", config)
    swept = Sweep(
        "leynos",
        "2026-11-16T04:17:00+00:00",
        "0.1.0",
        "e" * 40,
        RULES,
        (repo,),
        Excluded(0, 0, None),
    )
    write_site(swept, tmp_path)
    page = (tmp_path / "repos" / "demo.html").read_text("utf-8")
    assert "R-1" in page, "the finding code is on the detail page"
    assert 'id="always-red"' in page, "the rule has an anchor"
