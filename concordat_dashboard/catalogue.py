"""Describe the rule packages: their blocks, their applicability, their exemptions.

Concordat reports only compliant, non-compliant or indeterminate, so the
coupon's "not applicable" and "exempt" marks are derived here from two
declared facts: which repositories a rule is about, and which exemptions the
rule package ships. A package this table does not know is refused, so a new
rule cannot be dropped from the coupon silently.
"""

import dataclasses
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
    "spelling-config-baseline": Placement("HOUSE RULES", None),
    "yaml-lint-baseline": Placement("HOUSE RULES", None),
}


class UnknownPackageError(LookupError):
    """A concordat rule package has no place on the coupon."""


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

    Raises
    ------
    UnknownPackageError
        If the package is not in `PLACEMENTS`.
    """
    manifest = yaml.safe_load((package_dir / "rule.yaml").read_text("utf-8"))
    try:
        placement = PLACEMENTS[manifest["id"]]
    except KeyError as error:
        message = f"rule package {manifest['id']!r} has no placement in PLACEMENTS"
        raise UnknownPackageError(message) from error
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
        One column per package, ordered as `PLACEMENTS` orders them.

    Raises
    ------
    UnknownPackageError
        If a package is unknown, or a declared package is missing.
    """
    found = {
        info.id: info
        for path in sorted(packages_root.iterdir())
        if (path / "rule.yaml").is_file()
        for info in [read_rule_info(path)]
    }
    missing = PLACEMENTS.keys() - found.keys()
    if missing:
        message = f"declared rule packages are absent: {sorted(missing)}"
        raise UnknownPackageError(message)
    return tuple(found[rule_id] for rule_id in PLACEMENTS)


def exemptions_by_repository(
    defaults: cabc.Mapping[str, object],
) -> dict[str, tuple[Exemption, ...]]:
    """Group a package's shipped exemptions by `owner/name`.

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
        grouped.setdefault(entry["repository"], []).append(Exemption(where, rationale))
    return {repository: tuple(items) for repository, items in grouped.items()}
