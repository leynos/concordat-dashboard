"""The coupon's columns come from the installed concordat's rule packages."""

import typing as typ

import pytest

from concordat_dashboard.catalogue import (
    PLACEMENTS,
    ManifestMismatchError,
    ManifestMissingError,
    catalogue_notices,
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


def _package_root(root: pathlib.Path, *rule_ids: str) -> pathlib.Path:
    """Create one minimal package per id under *root*.

    Returns
    -------
    pathlib.Path
        *root*, now the packages root.
    """
    for rule_id in rule_ids:
        _write_package(root, rule_id)
    return root


def test_every_installed_package_becomes_a_column() -> None:
    """No package the installed concordat ships may be dropped from the coupon."""
    installed = {
        p.name for p in packages_root().iterdir() if (p / "rule.yaml").is_file()
    }
    assert {r.id for r in discover_rules(packages_root())} == installed, "columns"


def test_declared_columns_follow_placements_order() -> None:
    """Columns the table declares follow PLACEMENTS, not directory order."""
    rules = discover_rules(packages_root())
    declared = [r.id for r in rules if r.id in PLACEMENTS]
    assert declared == [i for i in PLACEMENTS if i in declared], "placements order"


def test_each_block_is_one_run_of_adjacent_columns() -> None:
    """A split block would repeat its heading on the coupon."""
    blocks = [placement.block for placement in PLACEMENTS.values()]
    runs = [block for i, block in enumerate(blocks) if i == 0 or block != blocks[i - 1]]
    assert len(runs) == len(set(runs)), f"a block is split across columns: {runs}"


def test_unknown_package_becomes_a_new_rules_column(tmp_path: pathlib.Path) -> None:
    """A package with no placement still appears, judged against every repository."""
    info = read_rule_info(_write_package(tmp_path, "brand-new-rule"))
    assert (info.block, info.applies_to) == ("NEW RULES", None), "unplaced column"


def test_unknown_package_is_noticed(tmp_path: pathlib.Path) -> None:
    """The catalogue reports an unplaced package; it does not print anything."""
    rules = discover_rules(
        _package_root(tmp_path, "uv-gate-baseline", "brand-new-rule")
    )
    notices = catalogue_notices(rules)
    unplaced = [n for n in notices if n.title == "Unplaced rule"]
    assert [n.message.split("'")[1] for n in unplaced] == ["brand-new-rule"], "named"


def test_a_manifest_naming_another_rule_is_refused(tmp_path: pathlib.Path) -> None:
    """A copied id would shadow the placed package's column."""
    package = _write_package(tmp_path, "brand-new-rule")
    (package / "rule.yaml").write_text(
        "id: uv-gate-baseline\nname: Imposter\nversion: 0.2.0\n", "utf-8"
    )
    with pytest.raises(ManifestMismatchError, match="brand-new-rule"):
        discover_rules(tmp_path)


def test_unknown_packages_follow_the_declared_ones_by_id(
    tmp_path: pathlib.Path,
) -> None:
    """New rules sort after every declared column, in a stable order."""
    ids = ("zzz-new", "uv-gate-baseline", "aaa-new", "yaml-lint-baseline")
    rules = discover_rules(_package_root(tmp_path, *ids))
    assert [r.id for r in rules] == [
        "uv-gate-baseline",
        "yaml-lint-baseline",
        "aaa-new",
        "zzz-new",
    ], "declared first, then new rules by id"


def test_a_policy_without_a_manifest_is_refused(tmp_path: pathlib.Path) -> None:
    """Concordat can run such a package, so omitting it would hide a rule."""
    (tmp_path / "manifestless" / "policy").mkdir(parents=True)
    with pytest.raises(ManifestMissingError, match="manifestless"):
        discover_rules(tmp_path)


def test_a_stray_directory_is_not_a_rule_package(tmp_path: pathlib.Path) -> None:
    """Only a manifest or a policy makes a directory a package."""
    (tmp_path / "__pycache__").mkdir()
    assert not discover_rules(tmp_path), "nothing but a stray directory"


@pytest.mark.parametrize(
    "shipped",
    [("uv-gate-baseline",), ("brand-new-rule",)],
    ids=["most-declared-dropped", "every-declared-dropped"],
)
def test_missing_declared_packages_are_dropped_and_noticed(
    tmp_path: pathlib.Path, shipped: tuple[str, ...]
) -> None:
    """Declared packages concordat no longer ships are dropped, with a notice."""
    rules = discover_rules(_package_root(tmp_path, *shipped))
    assert [r.id for r in rules] == list(shipped), "only what is shipped"
    absent = [n for n in catalogue_notices(rules) if n.title == "Absent rule"]
    assert len(absent) == 1, "one notice for the dropped packages"
    assert "yaml-lint-baseline" in absent[0].message, "a dropped package is named"


def test_a_complete_catalogue_has_no_notices() -> None:
    """When concordat and PLACEMENTS agree there is nothing to announce."""
    assert not catalogue_notices(discover_rules(packages_root())), "no gaps"


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
