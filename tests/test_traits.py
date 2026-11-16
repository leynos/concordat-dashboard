"""Trait detection decides only whether a clean verdict reads "not applicable"."""

import typing as typ

from concordat_dashboard.model import Trait
from concordat_dashboard.traits import detect_traits

if typ.TYPE_CHECKING:
    import pathlib


def _touch(root: pathlib.Path, relative: str, text: str = "") -> None:
    """Create a file, and its parents, under *root*."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")


def test_empty_tree_has_no_traits(tmp_path: pathlib.Path) -> None:
    """Nothing owned means no traits."""
    assert detect_traits(tmp_path) == frozenset(), "an empty tree has no traits"


def test_rust_source_marks_rust(tmp_path: pathlib.Path) -> None:
    """An owned .rs file marks the repository as Rust."""
    _touch(tmp_path, "src/lib.rs")
    assert detect_traits(tmp_path) == {Trait.RUST}, "a .rs file means Rust"


def test_vendored_source_is_ignored(tmp_path: pathlib.Path) -> None:
    """Somebody else's .rs file under vendor/ does not make a Rust repository."""
    _touch(tmp_path, "vendor/dep/lib.rs")
    _touch(tmp_path, "node_modules/x/y.py")
    assert detect_traits(tmp_path) == frozenset(), "vendored files must not count"


def test_pyproject_marks_python_and_uv(tmp_path: pathlib.Path) -> None:
    """A pyproject.toml is a Python project that the uv rules judge."""
    _touch(tmp_path, "pyproject.toml")
    found = detect_traits(tmp_path)
    assert found == {Trait.PYTHON, Trait.UV}, "pyproject.toml means Python and uv"


def test_makefile_running_uv_marks_uv_in_a_rust_repository(
    tmp_path: pathlib.Path,
) -> None:
    """A Rust repository whose Makefile runs uv is judged by the uv rules."""
    _touch(tmp_path, "src/lib.rs")
    _touch(tmp_path, "Makefile", "lint:\n\tuv tool run ruff check\n")
    found = detect_traits(tmp_path)
    assert found == {Trait.RUST, Trait.UV}, "a Makefile running uv means the uv trait"


def test_workflow_mentioning_uvx_marks_uv(tmp_path: pathlib.Path) -> None:
    """A workflow that runs uvx counts as running uv."""
    _touch(tmp_path, ".github/workflows/ci.yml", "run: uvx yamllint .\n")
    assert Trait.UV in detect_traits(tmp_path), "uvx in a workflow means the uv trait"


def test_word_uv_inside_another_word_is_not_uv(tmp_path: pathlib.Path) -> None:
    """Only the standalone word counts."""
    _touch(tmp_path, "Makefile", "all:\n\techo nuvola\n")
    assert detect_traits(tmp_path) == frozenset(), "nuvola is not uv"
