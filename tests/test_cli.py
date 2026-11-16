"""The commands write and read the sweep file and the site."""

import sys
import traceback
import typing as typ

import pytest

from concordat_dashboard import cli
from concordat_dashboard import estate as estate_module
from concordat_dashboard.estate import (
    Estate,
    IncompleteListingError,
    ListingFailedError,
)
from concordat_dashboard.model import Excluded
from concordat_dashboard.process import CommandFailedError
from concordat_dashboard.serialize import dumps, loads

if typ.TYPE_CHECKING:
    import pathlib

    from concordat_dashboard.model import Sweep
    from concordat_dashboard.sweep import SweepConfig


def test_render_writes_the_site_from_a_sweep_file(
    sweep: Sweep, tmp_path: pathlib.Path
) -> None:
    """`render` turns a persisted sweep into pages without sweeping again."""
    sweep_file = tmp_path / "sweep.json"
    sweep_file.write_text(dumps(sweep), "utf-8")
    site = str(tmp_path / "site")
    cli.app(["render", str(sweep_file), site], result_action="return_value")
    pages = sorted(p.name for p in (tmp_path / "site").rglob("*.html"))
    assert pages == ["index.html", "plain.html", "rusty.html"], "one page each"


def test_sweep_persists_what_the_sweep_returns(
    sweep: Sweep, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`sweep` writes the swept result, filtered by `--only`, as JSON."""
    seen: list[tuple[str, ...]] = []

    def run(_config: SweepConfig, estate: Estate, _workers: int) -> Sweep:
        """Record the repositories asked for and return the sample sweep.

        Returns
        -------
        Sweep
            The sample sweep.
        """
        seen.append(estate.names)
        return sweep

    everything = Estate(("plain", "rusty"), Excluded(0, 0, None))
    monkeypatch.setattr(cli, "list_estate", lambda *_args: everything)
    monkeypatch.setattr(cli, "build_config", lambda *_args: None)
    monkeypatch.setattr(cli, "run_sweep", run)
    out = tmp_path / "nested" / "sweep.json"
    cli.app(["sweep", str(out), "--only", "rusty"], result_action="return_value")
    assert seen == [("rusty",)], "only the named repository is swept"
    assert loads(out.read_text("utf-8")) == sweep, "the sweep is persisted"


def test_a_truncated_listing_stops_the_sweep_without_writing_a_file(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Partial coverage must never be written as a complete sweep."""

    def truncated(*_args: object) -> Estate:
        """Fail as a capped listing does.

        Raises
        ------
        IncompleteListingError
            Always.
        """
        message = "the listing reached its limit"
        raise IncompleteListingError(message)

    monkeypatch.setattr(cli, "list_estate", truncated)
    out = tmp_path / "sweep.json"
    with pytest.raises(IncompleteListingError):
        cli.app(["sweep", str(out)], result_action="return_value")
    assert not out.exists(), "no sweep file is written"


def test_a_failed_listing_exposes_no_gh_output_on_any_stream(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The stderr of `gh` may name a private repository; the CLI must not print it."""

    def refuse(*_args: str) -> str:
        """Fail as `gh repo list` with a revealing stderr would.

        Raises
        ------
        CommandFailedError
            Always.
        """
        full = "gh failed (1): could not resolve leynos/a-private-repository"
        raise CommandFailedError(full, "gh failed (1)")

    monkeypatch.setattr(estate_module, "gh", refuse)
    monkeypatch.setattr(
        sys, "argv", ["concordat-dashboard", "sweep", str(tmp_path / "s")]
    )
    with pytest.raises(ListingFailedError) as caught:
        cli.main()
    shown = "".join(traceback.format_exception(caught.value))
    streams = capsys.readouterr()
    everything = shown + streams.out + streams.err
    assert "a-private-repository" not in everything, "gh output reached a stream"
    assert "gh failed (1)" in shown, "the safe summary is reported"


def test_render_of_a_missing_sweep_file_fails(tmp_path: pathlib.Path) -> None:
    """A missing input is an error, not an empty site."""
    with pytest.raises(FileNotFoundError):
        cli.app(
            ["render", str(tmp_path / "absent.json"), str(tmp_path / "site")],
            result_action="return_value",
        )
    assert not (tmp_path / "site").exists(), "no site is written"
