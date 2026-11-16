"""A materialized tree is a git repository whose origin matches the GitHub slug."""

import typing as typ

import pytest

from concordat_dashboard.checkout import (
    checkout_tree,
    local_ref,
    materialize,
    origin_url,
)
from concordat_dashboard.process import CommandFailedError, git_in

if typ.TYPE_CHECKING:
    import collections.abc as cabc
    import pathlib

    type CloneFactory = cabc.Callable[[str, dict[str, str]], pathlib.Path]


def test_origin_url_is_the_canonical_https_clone_url() -> None:
    """Exemptions are keyed on this slug, so the URL shape matters."""
    url = origin_url("leynos", "whitaker")
    assert url == "https://github.com/leynos/whitaker.git", "canonical clone URL"


def test_local_ref_prefers_origin_head(clone: pathlib.Path) -> None:
    """A fresh clone has origin/HEAD."""
    assert local_ref(clone) == "origin/HEAD", "origin/HEAD is preferred"


def test_local_ref_falls_back_to_origin_main(clone: pathlib.Path) -> None:
    """A clone that never learnt origin/HEAD still has origin/main."""
    git_in(clone, "remote", "set-head", "origin", "--delete")
    assert local_ref(clone) == "origin/main", "origin/main is the fallback"


def test_local_ref_fails_without_a_default_branch(tmp_path: pathlib.Path) -> None:
    """A repository with neither ref is an error the sweep can report."""
    empty = tmp_path / "empty"
    empty.mkdir()
    git_in(empty, "init", "--quiet")
    with pytest.raises(CommandFailedError):
        local_ref(empty)


def test_materialize_checks_out_the_fetched_commit(
    clone: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """The tree holds the files and the returned SHA is the fetched commit."""
    dest = tmp_path / "tree"
    dest.mkdir()
    sha = materialize(str(clone), "origin/HEAD", dest)
    assert (dest / "README.md").read_text("utf-8") == "hello\n", "files are checked out"
    expected = git_in(clone, "rev-parse", "origin/HEAD").strip()
    assert sha == expected, "the returned SHA is the fetched commit"


def test_checkout_tree_sets_origin_so_exemptions_match(
    clone: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """The regression behind the sweep: an archive copy had no origin remote."""
    dest = tmp_path / "tree"
    dest.mkdir()
    checkout_tree("leynos", "demo", (str(clone), "origin/HEAD"), dest)
    url = git_in(dest, "remote", "get-url", "origin").strip()
    assert url == "https://github.com/leynos/demo.git", "origin must be the GitHub slug"


def test_checkout_survives_a_failing_lfs_filter(
    make_clone: CloneFactory,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A repository whose LFS objects cannot be fetched must still be checked out."""
    files = {".gitattributes": "*.bin filter=lfs -text\n", "pointer.bin": "x\n"}
    source = make_clone("lfs", files)
    # Make the smudge filter fail the way a missing git-lfs does.
    failing_filter = {
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "filter.lfs.smudge",
        "GIT_CONFIG_VALUE_0": "false",
        "GIT_CONFIG_KEY_1": "filter.lfs.required",
        "GIT_CONFIG_VALUE_1": "true",
    }
    for key, value in failing_filter.items():
        monkeypatch.setenv(key, value)
    dest = tmp_path / "tree"
    dest.mkdir()
    materialize(str(source), "HEAD", dest)
    assert (dest / "pointer.bin").is_file(), "the pointer file must be checked out"
