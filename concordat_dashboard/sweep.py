"""Sweep the estate: every repository against every functioning rule."""

import concurrent.futures as cf
import contextlib
import dataclasses
import datetime as dt
import functools
import pathlib
import tempfile
import typing as typ

from .catalogue import discover_rules, exemptions_by_repository
from .checkout import checkout_tree, local_ref, origin_url
from .classify import derive_cell
from .model import Cell, Exemption, Finding, RepoResult, RuleInfo, State, Sweep
from .process import CommandFailedError
from .runner import (
    Runner,
    concordat_identity,
    github_token,
    packages_root,
    rule_defaults,
)
from .traits import detect_traits

if typ.TYPE_CHECKING:
    import collections.abc as cabc

    from .estate import Estate

type ExemptionIndex = dict[str, dict[str, tuple[Exemption, ...]]]


@dataclasses.dataclass(frozen=True, slots=True)
class Locations:
    """The directories a sweep reads and writes."""

    workdir: pathlib.Path
    pin_cache_dir: pathlib.Path
    local_root: pathlib.Path | None = None
    keep_trees: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class SweepConfig:
    """Everything a worker needs to sweep one repository."""

    owner: str
    rules: tuple[RuleInfo, ...]
    exemptions: ExemptionIndex
    locations: Locations


@functools.cache
def _runner(pin_cache_dir: pathlib.Path) -> Runner:
    """Build one runner per worker process, so certification is shared.

    Returns
    -------
    Runner
        The process's runner.
    """
    return Runner(pin_cache_dir, github_token())


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
    clone = local_root / name
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
    return config.exemptions[rule_id].get(f"{config.owner}/{name}", ())


def _failed_result(name: str, config: SweepConfig, reason: str) -> RepoResult:
    """Mark every rule indeterminate for a repository that could not be fetched.

    Returns
    -------
    RepoResult
        A row of indeterminate cells, each carrying *reason*.
    """
    unproven = (Finding("ERROR", "", 0, reason),)
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
    runner = _runner(config.locations.pin_cache_dir)
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
        return _failed_result(name, config, f"the checkout failed: {error}")
    return RepoResult(name, sha, traits, cells)


def build_config(owner: str, locations: Locations) -> SweepConfig:
    """Discover the rules and their exemptions and bundle the sweep settings.

    Parameters
    ----------
    owner
        The GitHub owner being swept.
    locations
        The directories the sweep reads and writes.

    Returns
    -------
    SweepConfig
        Settings ready to hand to workers.
    """
    rules = discover_rules(packages_root())
    exemptions = {
        rule.id: exemptions_by_repository(rule_defaults(rule.id)) for rule in rules
    }
    return SweepConfig(owner, rules, exemptions, locations)


def run_sweep(config: SweepConfig, estate: Estate, workers: int) -> Sweep:
    """Sweep every repository in *estate*, in parallel across processes.

    Parameters
    ----------
    config
        The sweep settings.
    estate
        The repositories to sweep and the exclusion counts.
    workers
        How many repositories to sweep at once.

    Returns
    -------
    Sweep
        All results, rows in name order.
    """
    with cf.ProcessPoolExecutor(max_workers=workers) as pool:
        repos = tuple(
            pool.map(sweep_repository, estate.names, [config] * len(estate.names))
        )
    version, commit = concordat_identity()
    return Sweep(
        owner=config.owner,
        generated_at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        concordat_version=version,
        concordat_commit=commit,
        rules=config.rules,
        repos=repos,
        excluded=estate.excluded,
    )
