"""Command line: `sweep` the estate into a JSON file, then `render` the site."""

import dataclasses
import pathlib
import typing as typ

import cyclopts

from .estate import list_estate
from .render import write_site
from .serialize import dumps, loads
from .sweep import Locations, build_config, run_sweep

app = cyclopts.App(
    name="concordat-dashboard",
    help="Sweep the estate against concordat's rules and publish a coupon.",
)


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class SweepOptions:
    """Where to sweep and how.

    Attributes
    ----------
    owner
        The GitHub owner whose public repositories are swept.
    workdir
        Scratch directory for checkouts.
    pin_cache
        Directory caching action-pin lookups between runs.
    local_root
        Sweep local clones under this directory instead of fetching from GitHub.
    workers
        Repositories swept at once.
    keep_trees
        Keep each checkout after it is swept (otherwise it is removed).
    hidden_private
        Private repositories invisible to this token, for the page's count.
    only
        Sweep just these repositories (for development).
    """

    owner: str = "leynos"
    workdir: pathlib.Path = pathlib.Path(".work/trees")
    pin_cache: pathlib.Path = pathlib.Path(".work/pins")
    local_root: pathlib.Path | None = None
    workers: int = 4
    keep_trees: bool = False
    hidden_private: int | None = None
    only: tuple[str, ...] = ()


DEFAULTS = SweepOptions()


def _sweep(options: SweepOptions) -> str:
    """Run the sweep and return it as JSON.

    Returns
    -------
    str
        The serialized sweep.
    """
    locations = Locations(
        options.workdir, options.pin_cache, options.local_root, options.keep_trees
    )
    estate = list_estate(options.owner, options.hidden_private)
    if options.only:
        estate = dataclasses.replace(
            estate, names=tuple(n for n in estate.names if n in options.only)
        )
    config = build_config(options.owner, locations)
    return dumps(run_sweep(config, estate, options.workers))


@app.command
def sweep(
    sweep_file: pathlib.Path,
    options: typ.Annotated[SweepOptions, cyclopts.Parameter(name="*")] = DEFAULTS,
) -> None:
    """Sweep the estate and write the results as JSON.

    Parameters
    ----------
    sweep_file
        Where to write the sweep.
    options
        Where to sweep and how.
    """
    sweep_file.parent.mkdir(parents=True, exist_ok=True)
    sweep_file.write_text(_sweep(options), "utf-8")


@app.command
def render(sweep_file: pathlib.Path, out: pathlib.Path) -> None:
    """Render a sweep file into the static site.

    Parameters
    ----------
    sweep_file
        A file written by `sweep`.
    out
        The site directory.
    """
    count = write_site(loads(sweep_file.read_text("utf-8")), out)
    print(f"wrote {count} pages to {out}")


def main() -> None:
    """Run the command line."""
    app()
