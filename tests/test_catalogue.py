"""The coupon's columns come from the installed concordat's rule packages."""

import typing as typ

import pytest

from concordat_dashboard.catalogue import (
    PLACEMENTS,
    ManifestMissingError,
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


def test_unknown_package_becomes_a_new_rules_column(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A package with no placement still appears, and the run says so."""
    package = _write_package(tmp_path, "brand-new-rule")
    info = read_rule_info(package)
    assert (info.block, info.applies_to) == ("NEW RULES", None), "unplaced column"
    err = capsys.readouterr().err
    assert "::warning title=Unplaced rule::" in err, "a workflow annotation"
    assert "brand-new-rule" in err, "the annotation names the package"


def test_unknown_packages_follow_the_declared_ones_by_id(
    tmp_path: pathlib.Path,
) -> None:
    """New rules sort after every declared column, in a stable order."""
    for rule_id in ("zzz-new", "uv-gate-baseline", "aaa-new", "yaml-lint-baseline"):
        _write_package(tmp_path, rule_id)
    rules = discover_rules(tmp_path)
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


def test_missing_declared_package_is_dropped_with_a_warning(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A declared package that concordat no longer ships is dropped, loudly."""
    _write_package(tmp_path, "uv-gate-baseline")
    rules = discover_rules(tmp_path)
    assert [r.id for r in rules] == ["uv-gate-baseline"], "only what is shipped"
    assert "::warning title=Absent rule::" in capsys.readouterr().err, "annotation"


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
