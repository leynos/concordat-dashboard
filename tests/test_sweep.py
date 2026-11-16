"""One repository is fetched, judged by every rule, and marked."""

import concurrent.futures as cf
import dataclasses
import datetime as dt
import pathlib
import typing as typ

import pytest

from concordat_dashboard import cli
from concordat_dashboard import sweep as sweep_module
from concordat_dashboard.catalogue import PLACEMENTS
from concordat_dashboard.classify import RawFinding
from concordat_dashboard.estate import Estate, classify_repositories
from concordat_dashboard.model import Excluded, Exemption, RuleInfo, State, Trait
from concordat_dashboard.sweep import (
    Clocks,
    Locations,
    SweepConfig,
    SweepDegradedError,
    build_config,
    log_outcome,
    run_sweep,
    sweep_repository,
)

if typ.TYPE_CHECKING:
    import collections.abc as cabc

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


def _config(root: pathlib.Path, runner: type = FakeRunner) -> SweepConfig:
    """Build a config sweeping local clones under *root* with a stub runner.

    Returns
    -------
    SweepConfig
        The config; its `runner_factory` builds *runner*, so no rule package or
        network is needed.
    """
    exemptions: ExemptionIndex = {
        "always-red": {},
        "rusty-only": {},
        "exempted": {"leynos/demo": (Exemption("p", "why"),)},
    }
    locations = Locations(root / "work", root / "pins", root)
    return SweepConfig(
        "leynos",
        RULES,
        exemptions,
        locations,
        runner_factory=lambda *_args: runner(),
    )


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


def test_unreadable_repository_is_all_indeterminate_not_a_crash(
    clone: pathlib.Path,
) -> None:
    """A read error in one repository must not stop the estate sweep."""
    result = sweep_repository("demo", _config(clone.parent, UnreadableRunner))
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
    clone: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    failing_with: cabc.Callable[[str], cabc.Callable[..., str]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A command's stderr may name a private repository; only its summary is shown."""
    monkeypatch.setattr(sweep_module, "checkout_tree", failing_with("git failed (128)"))
    with caplog.at_level("INFO"):
        result = sweep_repository("demo", _config(clone.parent))
    message = result.cells["always-red"].unproven[0].message
    assert "git failed (128)" in message, "the summary is published"
    assert "a-private-repository" not in message, "command output must not be"
    assert "a-private-repository" not in caplog.text, "nor may the run log carry it"


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


@pytest.fixture
def in_process_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the sweep's "process" pool on threads, so stubs reach the workers."""
    monkeypatch.setattr(cf, "ProcessPoolExecutor", cf.ThreadPoolExecutor)


@pytest.mark.usefixtures("in_process_pool")
def test_run_sweep_uses_the_injected_clock_and_keeps_the_estate_counts(
    clone: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The sweep's timestamp, exclusions and row order come from its inputs."""
    estate = Estate(("zzz-ghost", "demo"), Excluded(2, 1, 7, 3))
    moment = dt.datetime(2026, 11, 16, 4, 17, tzinfo=dt.UTC)
    ticks = iter([100.0, 142.0])
    clocks = Clocks(now=lambda: moment, monotonic=lambda: next(ticks))
    with caplog.at_level("INFO"):
        swept = run_sweep(_config(clone.parent), estate, 2, clocks)
    assert swept.generated_at == "2026-11-16T04:17:00+00:00", "injected clock"
    assert swept.excluded == Excluded(2, 1, 7, 3), "exclusions pass through"
    assert [r.name for r in swept.repos] == ["demo", "zzz-ghost"], "name order"
    assert len(swept.concordat_commit) == 40, "the pinned commit is recorded"
    expected = (
        "swept 2 repositories in 42s",
        "noncompliant",
        "DEGRADED: 1 of 2 repositories failed",
    )
    missing = [line for line in expected if line not in caplog.text]
    assert not missing, f"the closing log lacks: {missing}"


def test_a_fully_degraded_run_is_an_error_and_a_partial_one_is_not(
    clone: pathlib.Path,
) -> None:
    """When nothing could be swept there is nothing to publish; the page stays."""
    config = _config(clone.parent)
    ghost = sweep_repository("ghost", config)
    good = sweep_repository("demo", config)
    with pytest.raises(SweepDegradedError, match="all 1 repositories"):
        log_outcome((ghost,), 1.0)
    log_outcome((ghost, good), 1.0)
    log_outcome((), 0.0)


@pytest.mark.usefixtures("in_process_pool")
def test_cli_sweep_then_render_publishes_the_finding_text(
    clone: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole path: list, sweep, persist as JSON, render pages from the file."""
    row = {"name": "demo", "isFork": False, "isArchived": False, "visibility": "PUBLIC"}
    monkeypatch.setattr(
        cli,
        "list_estate",
        lambda _owner, hidden: classify_repositories([row], hidden),
    )
    monkeypatch.setattr(cli, "build_config", lambda *_args: _config(clone.parent))
    sweep_file, site = tmp_path / "sweep.json", tmp_path / "site"
    cli.app(
        ["sweep", str(sweep_file), "--hidden-private", "11"],
        result_action="return_value",
    )
    cli.app(["render", str(sweep_file), str(site)], result_action="return_value")
    page = (site / "repos" / "demo.html").read_text("utf-8")
    index = (site / "index.html").read_text("utf-8")
    assert "R-1" in page, "the finding code is on the detail page"
    assert 'id="always-red"' in page, "the rule has an anchor"
    assert "11 private repositories not shown" in index, "--hidden-private reaches it"


def test_build_config_discovers_the_pinned_rules_and_hides_the_token(
    tmp_path: pathlib.Path,
) -> None:
    """The config carries every pinned rule, its exemptions and a hidden token."""
    config = build_config("leynos", Locations(tmp_path, tmp_path), "s3cr3t-token")
    assert len(config.rules) == len(PLACEMENTS), "one rule per placed package"
    assert "leynos/netsuke" in config.exemptions["nested-cargo-nextest"], "exemptions"
    assert "s3cr3t-token" not in repr(config), "the token must not appear in a repr"
