"""A materialised tree is a git repository whose origin matches the GitHub slug."""

import typing as typ

import pytest

from concordat_dashboard.checkout import (
    checkout_tree,
    local_ref,
    materialise,
    origin_url,
)
from concordat_dashboard.process import CommandFailedError, git, git_in

if typ.TYPE_CHECKING:
    import pathlib

AUTHOR = ("-c", "user.name=t", "-c", "user.email=t@example.invalid")


@pytest.fixture
def clone(tmp_path: pathlib.Path) -> pathlib.Path:
    """Provide a local clone with one commit on a branch known as origin/main.

    Returns
    -------
    pathlib.Path
        The clone.
    """
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git_in(upstream, "init", "--quiet", "--initial-branch", "main")
    (upstream / "README.md").write_text("hello\n", "utf-8")
    git_in(upstream, "add", ".")
    git_in(upstream, *AUTHOR, "commit", "--quiet", "-m", "first")
    target = tmp_path / "clone"
    git("clone", "--quiet", str(upstream), str(target))
    return target


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


def test_materialise_checks_out_the_fetched_commit(
    clone: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """The tree holds the files and the returned SHA is the fetched commit."""
    dest = tmp_path / "tree"
    dest.mkdir()
    sha = materialise(str(clone), "origin/HEAD", dest)
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
