"""The coupon's columns come from the installed concordat's rule packages."""

import typing as typ

import pytest

from concordat_dashboard.catalogue import (
    PLACEMENTS,
    UnknownPackageError,
    discover_rules,
    exemptions_by_repository,
    read_rule_info,
)
from concordat_dashboard.model import Trait
from concordat_dashboard.runner import packages_root, rule_defaults

if typ.TYPE_CHECKING:
    import pathlib


def _write_package(root: pathlib.Path, rule_id: str) -> pathlib.Path:
    """Create a minimal rule package directory.

    Returns
    -------
    pathlib.Path
        The package directory.
    """
    package = root / rule_id
    package.mkdir(parents=True)
    (package / "rule.yaml").write_text(
        f"id: {rule_id}\nname: Name of {rule_id}\nversion: 0.2.0\n", "utf-8"
    )
    return package


def test_every_installed_package_has_a_placement() -> None:
    """A new concordat package must be placed on the coupon deliberately."""
    installed = {
        p.name for p in packages_root().iterdir() if (p / "rule.yaml").is_file()
    }
    assert installed == set(PLACEMENTS), "concordat and PLACEMENTS disagree"


def test_discovery_orders_columns_as_declared() -> None:
    """Columns follow PLACEMENTS, not directory order."""
    rules = discover_rules(packages_root())
    assert [r.id for r in rules] == list(PLACEMENTS), "columns must follow PLACEMENTS"


def test_unknown_package_is_refused(tmp_path: pathlib.Path) -> None:
    """A package with no placement fails loudly rather than vanishing."""
    package = _write_package(tmp_path, "brand-new-rule")
    with pytest.raises(UnknownPackageError, match="brand-new-rule"):
        read_rule_info(package)


def test_missing_declared_package_is_refused(tmp_path: pathlib.Path) -> None:
    """A declared package that concordat no longer ships fails loudly."""
    _write_package(tmp_path, "uv-gate-baseline")
    with pytest.raises(UnknownPackageError, match="absent"):
        discover_rules(tmp_path)


def test_rule_info_reads_manifest_and_placement(tmp_path: pathlib.Path) -> None:
    """Name and version come from the manifest; block and trait from the table."""
    info = read_rule_info(_write_package(tmp_path, "uv-gate-baseline"))
    assert (info.name, info.version) == ("Name of uv-gate-baseline", "0.2.0"), (
        "name and version come from the manifest"
    )
    assert (info.block, info.applies_to) == ("PYTHON", Trait.UV), (
        "block and trait come from PLACEMENTS"
    )


def test_exemptions_group_by_repository_and_normalize_text() -> None:
    """Exemptions key on owner/name; rationale whitespace is collapsed."""
    defaults = {
        "exemptions": [
            {"repository": "o/a", "path": "x.rs", "rationale": "two\n  lines"},
            {"repository": "o/a", "directory": "d", "rationale": "dir"},
            {"repository": "o/b", "path": "y.rs", "rationale": "other"},
        ]
    }
    grouped = exemptions_by_repository(defaults)
    assert [e.path for e in grouped["o/a"]] == ["x.rs", "d"], "path or directory"
    assert grouped["o/a"][0].rationale == "two lines", "whitespace is collapsed"
    assert set(grouped) == {"o/a", "o/b"}, "one key per repository"


def test_exemption_keys_are_lower_case() -> None:
    """GitHub names are case-insensitive, so the index must be too."""
    defaults = {"exemptions": [{"repository": "Leynos/Netsuke", "path": "p"}]}
    assert set(exemptions_by_repository(defaults)) == {"leynos/netsuke"}, "key case"


def test_package_without_exemptions_yields_none() -> None:
    """A package that ships no exemptions has an empty index."""
    assert exemptions_by_repository({}) == {}, "no exemptions means an empty index"


def test_nested_cargo_nextest_ships_a_netsuke_exemption() -> None:
    """The installed concordat's real defaults reach the index."""
    grouped = exemptions_by_repository(rule_defaults("nested-cargo-nextest"))
    assert "leynos/netsuke" in grouped, "the shipped netsuke exemption must be read"
