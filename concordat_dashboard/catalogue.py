"""Describe the rule packages: their blocks, their applicability, their exemptions.

Concordat reports only compliant, non-compliant or indeterminate, so the
coupon's "not applicable" and "exempt" marks are derived here from two
declared facts: which repositories a rule is about, and which exemptions the
rule package ships. The sweep installs concordat's main on every run, so a rule
can arrive before this table knows it: such a package still becomes a column,
in the `NEW RULES` block and judged against every repository, and the run
raises a workflow warning asking for a placement. A declared package that
concordat no longer ships is dropped with a warning. Neither case fails the
run, because a coupon with a missing rule would be worse than a plain column.
"""

import dataclasses
import sys
import typing as typ

import yaml

from .model import Exemption, RuleInfo, Trait

if typ.TYPE_CHECKING:
    import collections.abc as cabc
    import pathlib


@dataclasses.dataclass(frozen=True, slots=True)
class Placement:
    """Where a rule sits on the coupon and whom it is about."""

    block: str
    applies_to: Trait | None


# The order here is the order of the columns on the page.
PLACEMENTS: typ.Final[dict[str, Placement]] = {
    "dependabot-update-shape": Placement("UPDATES", None),
    "dependency-family-contracts": Placement("UPDATES", None),
    "rust-build-defaults": Placement("RUST BUILD", Trait.RUST),
    "rust-dev-build-footprint": Placement("RUST BUILD", Trait.RUST),
    "rust-makefile-baseline": Placement("RUST BUILD", Trait.RUST),
    "rust-prover-tooling": Placement("RUST BUILD", Trait.RUST),
    "rust-test-environment": Placement("RUST BUILD", Trait.RUST),
    "rust-toolchain-policy": Placement("RUST BUILD", Trait.RUST),
    "whitaker-provisioning": Placement("RUST BUILD", Trait.RUST),
    "nested-cargo-ci-wiring": Placement("NESTED CARGO", Trait.RUST),
    "gate-workspace-coverage": Placement("RUST BUILD", Trait.RUST),
    "nested-cargo-cold-build": Placement("NESTED CARGO", Trait.RUST),
    "nested-cargo-fixture-lockfiles": Placement("NESTED CARGO", Trait.RUST),
    "nested-cargo-fixture-manifests": Placement("NESTED CARGO", Trait.RUST),
    "nested-cargo-nextest": Placement("NESTED CARGO", Trait.RUST),
    "nested-cargo-offline-tests": Placement("NESTED CARGO", Trait.RUST),
    # The uv rules judge any repository that runs uv, Rust ones included.
    "uv-gate-baseline": Placement("PYTHON", Trait.UV),
    "python-duplication-gate": Placement("PYTHON", Trait.PYTHON),
    "documentation-presence": Placement("PYTHON", None),
    "main-owned-codescene-coverage": Placement("HOUSE RULES", None),
    "markdown-formatting-baseline": Placement("HOUSE RULES", None),
    "pr-run-cancellation": Placement("HOUSE RULES", None),
    "spelling-config-baseline": Placement("HOUSE RULES", None),
    "yaml-lint-baseline": Placement("HOUSE RULES", None),
}


UNPLACED: typ.Final = Placement("NEW RULES", None)


def _warn(title: str, message: str) -> None:
    """Raise a workflow annotation, so a catalogue gap is visible in the run."""
    sys.stderr.write(f"::warning title={title}::{message}\n")


def read_rule_info(package_dir: pathlib.Path) -> RuleInfo:
    """Read one rule package's manifest into a coupon column.

    Parameters
    ----------
    package_dir
        The rule package directory, holding `rule.yaml`.

    Returns
    -------
    RuleInfo
        The column for the package.

    Notes
    -----
    A package not in `PLACEMENTS` is placed in the `NEW RULES` block and
    announced with a workflow warning.
    """
    manifest = yaml.safe_load((package_dir / "rule.yaml").read_text("utf-8"))
    placement = PLACEMENTS.get(manifest["id"])
    if placement is None:
        placement = UNPLACED
        _warn(
            "Unplaced rule",
            f"rule package {manifest['id']!r} has no placement in PLACEMENTS;"
            " shown under NEW RULES",
        )
    return RuleInfo(
        id=manifest["id"],
        name=manifest["name"],
        version=str(manifest["version"]),
        block=placement.block,
        applies_to=placement.applies_to,
    )


def discover_rules(packages_root: pathlib.Path) -> tuple[RuleInfo, ...]:
    """List every rule package under *packages_root* in coupon order.

    Parameters
    ----------
    packages_root
        The directory holding one subdirectory per rule package.

    Returns
    -------
    tuple[RuleInfo, ...]
        One column per package: those `PLACEMENTS` declares in its order, then
        any package it does not know, by id.
    """
    found = {
        info.id: info
        for path in sorted(packages_root.iterdir())
        if (path / "rule.yaml").is_file()
        for info in [read_rule_info(path)]
    }
    missing = PLACEMENTS.keys() - found.keys()
    if missing:
        _warn(
            "Absent rule",
            f"declared rule packages are no longer shipped: {sorted(missing)}",
        )
    declared = [found[rule_id] for rule_id in PLACEMENTS if rule_id in found]
    new = [found[rule_id] for rule_id in sorted(found.keys() - PLACEMENTS.keys())]
    return tuple(declared + new)


def exemptions_by_repository(
    defaults: cabc.Mapping[str, object],
) -> dict[str, tuple[Exemption, ...]]:
    """Group a package's shipped exemptions by lower-case `owner/name`.

    Parameters
    ----------
    defaults
        The package's manifest parameter defaults.

    Returns
    -------
    dict[str, tuple[Exemption, ...]]
        Exemptions keyed by the repository they name; empty for a package that
        ships none.
    """
    grouped: dict[str, list[Exemption]] = {}
    for entry in typ.cast("list[dict[str, str]]", defaults.get("exemptions") or []):
        where = entry.get("path") or entry.get("directory") or ""
        rationale = " ".join(entry.get("rationale", "").split())
        slug = entry["repository"].lower()
        grouped.setdefault(slug, []).append(Exemption(where, rationale))
    return {repository: tuple(items) for repository, items in grouped.items()}
