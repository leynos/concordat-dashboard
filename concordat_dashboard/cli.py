"""Command line: `sweep` the estate into a JSON file, then `render` the site."""

import dataclasses
import logging
import pathlib
import sys
import typing as typ

import cyclopts

from .estate import list_estate
from .render import write_site
from .runner import UNKNOWN_COMMIT, concordat_identity, github_token
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
    config = build_config(options.owner, locations, github_token())
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


@app.command
def concordat() -> None:
    """Print the concordat version and commit that supply the rules.

    The scheduled workflow records this line, so the run shows which concordat
    commit it swept with. A concordat that was not installed from a git
    reference has no commit to name, so the command fails rather than let a
    coupon claim rules it cannot identify.

    Raises
    ------
    SystemExit
        If the installed concordat has no commit identity.
    """
    version, commit = concordat_identity()
    if commit == UNKNOWN_COMMIT:
        sys.stderr.write("::error title=Unknown concordat::no commit identity\n")
        raise SystemExit(1)
    print(f"concordat {version} @ {commit}")


def main() -> None:
    """Run the command line, logging sweep progress (public names only)."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    app()
