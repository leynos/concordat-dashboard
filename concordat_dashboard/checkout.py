"""Materialise a repository's default-branch tree for the rules to read.

Both the scheduled run (shallow fetch from GitHub) and a local run (fetch from
a clone under the projects directory) end in the same shape: a fresh git
repository whose `origin` is the GitHub URL. Concordat keys exemptions on the
`origin` slug, so a tree without that remote would silently skip them.
"""

import typing as typ

from .process import CommandFailedError, git_in

if typ.TYPE_CHECKING:
    import pathlib

GITHUB = "https://github.com"


def origin_url(owner: str, name: str) -> str:
    """Return the canonical clone URL concordat reads exemptions from.

    Parameters
    ----------
    owner
        The GitHub owner.
    name
        The repository name.

    Returns
    -------
    str
        The HTTPS clone URL.

    Examples
    --------
    >>> origin_url("leynos", "whitaker")
    'https://github.com/leynos/whitaker.git'
    """
    return f"{GITHUB}/{owner}/{name}.git"


def materialise(source: str, ref: str, dest: pathlib.Path) -> str:
    """Fetch *ref* from *source* into a new repository at *dest*.

    Parameters
    ----------
    source
        A clone URL or a local clone path.
    ref
        The ref to fetch, such as `HEAD` or `refs/remotes/origin/HEAD`.
    dest
        An existing, empty directory.

    Returns
    -------
    str
        The commit SHA now checked out.
    """
    git_in(dest, "init", "--quiet")
    git_in(dest, "fetch", "--quiet", "--depth", "1", source, ref)
    git_in(dest, "checkout", "--quiet", "FETCH_HEAD")
    return git_in(dest, "rev-parse", "HEAD").strip()


def local_ref(clone: pathlib.Path) -> str:
    """Pick the default-branch ref of a local clone.

    Parameters
    ----------
    clone
        A local clone with an `origin` remote.

    Returns
    -------
    str
        `origin/HEAD` when the clone knows it, else `origin/main`.

    Raises
    ------
    CommandFailedError
        If the clone has neither ref.
    """
    for candidate in ("origin/HEAD", "origin/main"):
        try:
            git_in(clone, "rev-parse", "--verify", "--quiet", candidate)
        except CommandFailedError:
            continue
        return candidate
    message = f"{clone} has neither origin/HEAD nor origin/main"
    raise CommandFailedError(message)


def checkout_tree(
    owner: str,
    name: str,
    source: tuple[str, str],
    dest: pathlib.Path,
) -> str:
    """Fetch one repository's default branch into *dest* and set its `origin`.

    Parameters
    ----------
    owner
        The GitHub owner, for the `origin` URL.
    name
        The repository name, for the `origin` URL.
    source
        The clone location (URL or path) and the ref to fetch from it.
    dest
        An existing, empty directory.

    Returns
    -------
    str
        The commit SHA checked out.
    """
    sha = materialise(source[0], source[1], dest)
    git_in(dest, "remote", "add", "origin", origin_url(owner, name))
    return sha
