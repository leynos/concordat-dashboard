"""Sweep the estate: every repository against every functioning rule."""

import collections
import concurrent.futures as cf
import contextlib
import dataclasses
import datetime as dt
import functools
import logging
import pathlib
import tempfile
import typing as typ

from .catalogue import discover_rules, exemptions_by_repository
from .checkout import checkout_tree, local_ref, origin_url
from .classify import RawFinding, derive_cell
from .model import Cell, Exemption, Finding, RepoResult, RuleInfo, State, Sweep
from .process import CommandFailedError
from .redact import public_reason
from .runner import (
    Runner,
    concordat_identity,
    packages_root,
    rule_defaults,
)
from .traits import detect_traits

if typ.TYPE_CHECKING:
    import collections.abc as cabc

    from .estate import Estate

LOG = logging.getLogger(__name__)

type ExemptionIndex = dict[str, dict[str, tuple[Exemption, ...]]]


@dataclasses.dataclass(frozen=True, slots=True)
class Locations:
    """The directories a sweep reads and writes."""

    workdir: pathlib.Path
    pin_cache_dir: pathlib.Path
    local_root: pathlib.Path | None = None
    keep_trees: bool = False


class RuleRunner(typ.Protocol):
    """Runs one rule against one checkout."""

    def run(self, rule_id: str, tree: pathlib.Path) -> tuple[RawFinding, ...]:
        """Return the rule's findings for the checkout."""
        ...


type RunnerFactory = cabc.Callable[[pathlib.Path, str | None], RuleRunner]


@functools.cache
def shared_runner(pin_cache_dir: pathlib.Path, token: str | None) -> Runner:
    """Build one runner per worker process, so certification is shared.

    Returns
    -------
    Runner
        The process's runner.
    """
    return Runner(pin_cache_dir, token)


@dataclasses.dataclass(frozen=True, slots=True)
class SweepConfig:
    """Everything a worker needs to sweep one repository."""

    owner: str
    rules: tuple[RuleInfo, ...]
    exemptions: ExemptionIndex
    locations: Locations
    # Never shown in a repr or a log line.
    token: str | None = dataclasses.field(default=None, repr=False)
    # Injectable so a test needs no rule package or network.
    runner_factory: RunnerFactory = shared_runner


@contextlib.contextmanager
def _tree_dir(config: SweepConfig) -> cabc.Iterator[pathlib.Path]:
    """Yield an empty directory for one checkout; remove it unless kept.

    Yields
    ------
    pathlib.Path
        The empty directory.
    """
    where = config.locations
    where.workdir.mkdir(parents=True, exist_ok=True)
    if where.keep_trees:
        yield pathlib.Path(tempfile.mkdtemp(dir=where.workdir))
        return
    with tempfile.TemporaryDirectory(dir=where.workdir) as raw:
        yield pathlib.Path(raw)


def _source(name: str, config: SweepConfig) -> tuple[str, str]:
    """Pick where to fetch a repository from: a local clone, else GitHub.

    Returns
    -------
    tuple[str, str]
        The clone location and the ref to fetch.
    """
    local_root = config.locations.local_root
    if local_root is None:
        return origin_url(config.owner, name), "HEAD"
    # The fetch runs inside the destination, so a relative path would resolve
    # against that directory instead of the caller's.
    clone = (local_root / name).resolve()
    return str(clone), local_ref(clone)


def _exemptions_for(
    config: SweepConfig, rule_id: str, name: str
) -> tuple[Exemption, ...]:
    """Return the shipped exemptions a rule has on record for a repository.

    Returns
    -------
    tuple[Exemption, ...]
        The exemptions; empty when there are none.
    """
    # GitHub treats owner and repository names as case-insensitive, and the
    # index is keyed in lower case.
    return config.exemptions[rule_id].get(f"{config.owner}/{name}".lower(), ())


def _failed_result(name: str, config: SweepConfig, reason: str) -> RepoResult:
    """Mark every rule indeterminate for a repository that could not be fetched.

    Returns
    -------
    RepoResult
        A row of indeterminate cells, each carrying *reason*.
    """
    unproven = (Finding("ERROR", "", 0, public_reason(reason)),)
    cells = {r.id: Cell(State.INDETERMINATE, unproven=unproven) for r in config.rules}
    return RepoResult(name, "unknown", frozenset(), cells)


def sweep_repository(name: str, config: SweepConfig) -> RepoResult:
    """Judge one repository against every rule.

    Parameters
    ----------
    name
        The repository name.
    config
        The rules, exemptions and locations for this sweep.

    Returns
    -------
    RepoResult
        One cell per rule. A repository that cannot be fetched comes back with
        every cell indeterminate and the reason, rather than failing the sweep.
    """
    runner = config.runner_factory(config.locations.pin_cache_dir, config.token)
    try:
        with _tree_dir(config) as dest:
            sha = checkout_tree(config.owner, name, _source(name, config), dest)
            traits = detect_traits(dest)
            cells = {
                rule.id: derive_cell(
                    rule,
                    runner.run(rule.id, dest),
                    (traits, _exemptions_for(config, rule.id, name)),
                )
                for rule in config.rules
            }
    except CommandFailedError as error:
        # Page and log alike get the summary only: the command's own output
        # could name something that must not be published.
        reason = f"the checkout failed: {error.public_summary}"
        LOG.warning("%s: %s", name, public_reason(reason))
        return _failed_result(name, config, reason)
    except OSError as error:
        # An unreadable file in one repository must not stop the estate sweep.
        reason = f"the repository could not be read ({type(error).__name__})"
        LOG.warning("%s: %s", name, public_reason(reason))
        return _failed_result(name, config, reason)
    return RepoResult(name, sha, traits, cells)


def build_config(
    owner: str, locations: Locations, token: str | None = None
) -> SweepConfig:
    """Discover the rules and their exemptions and bundle the sweep settings.

    Parameters
    ----------
    owner
        The GitHub owner being swept.
    locations
        The directories the sweep reads and writes.
    token
        The GitHub token the rules' pin and certification lookups use.

    Returns
    -------
    SweepConfig
        Settings ready to hand to workers.
    """
    rules = discover_rules(packages_root())
    exemptions = {
        rule.id: exemptions_by_repository(rule_defaults(rule.id)) for rule in rules
    }
    return SweepConfig(owner, rules, exemptions, locations, token)


def _utc_now() -> dt.datetime:
    """Return the current time in UTC.

    Returns
    -------
    dt.datetime
        The time now.
    """
    return dt.datetime.now(dt.UTC)


def collect(
    pool: cf.Executor, names: tuple[str, ...], config: SweepConfig
) -> tuple[RepoResult, ...]:
    """Sweep *names* on *pool*, logging each repository as it finishes.

    Only public repository names are logged, so the run log is safe to read.

    Returns
    -------
    tuple[RepoResult, ...]
        The results in name order, whatever order they finished in.
    """
    futures = [pool.submit(sweep_repository, name, config) for name in names]
    results = []
    for done, future in enumerate(cf.as_completed(futures), 1):
        result = future.result()
        LOG.info("swept %d/%d: %s", done, len(futures), result.name)
        results.append(result)
    return tuple(sorted(results, key=lambda r: r.name))


def log_outcome(repos: tuple[RepoResult, ...], elapsed: dt.timedelta) -> None:
    """Log how long the sweep took and how its marks came out.

    Counts only: nothing here names a repository.

    Parameters
    ----------
    repos
        The swept repositories.
    elapsed
        How long the sweep took.
    """
    totals = collections.Counter(
        cell.state.value for repo in repos for cell in repo.cells.values()
    )
    LOG.info(
        "swept %d repositories in %.0fs: %s",
        len(repos),
        elapsed.total_seconds(),
        ", ".join(f"{count} {state}" for state, count in sorted(totals.items())),
    )


def run_sweep(
    config: SweepConfig,
    estate: Estate,
    workers: int,
    clock: cabc.Callable[[], dt.datetime] = _utc_now,
) -> Sweep:
    """Sweep every repository in *estate*, in parallel across processes.

    Parameters
    ----------
    config
        The sweep settings.
    estate
        The repositories to sweep and the exclusion counts.
    workers
        How many repositories to sweep at once.
    clock
        Supplies the sweep's timestamp; injectable so a test is deterministic.

    Returns
    -------
    Sweep
        All results, rows in name order.
    """
    started = clock()
    with cf.ProcessPoolExecutor(max_workers=workers) as pool:
        repos = collect(pool, estate.names, config)
    finished = clock()
    log_outcome(repos, finished - started)
    version, commit = concordat_identity()
    return Sweep(
        owner=config.owner,
        generated_at=finished.isoformat(timespec="seconds"),
        concordat_version=version,
        concordat_commit=commit,
        rules=config.rules,
        repos=repos,
        excluded=estate.excluded,
    )
