"""The commands write and read the sweep file and the site."""

import typing as typ

from concordat_dashboard import cli
from concordat_dashboard.estate import Estate
from concordat_dashboard.model import Excluded
from concordat_dashboard.serialize import dumps, loads

if typ.TYPE_CHECKING:
    import pathlib

    import pytest

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
