"""Decide which repositories the sweep covers, and count the ones it leaves out.

Only public, active, non-fork repositories are swept. A private repository is
counted but never named: the page is public, so its name must not reach any
output, including the sweep file.
"""

import dataclasses
import json
import typing as typ

from .model import Excluded
from .process import gh

PUBLIC = "PUBLIC"
LIST_FIELDS = "name,isFork,isArchived,visibility"
LIST_LIMIT = "1000"


@dataclasses.dataclass(frozen=True, slots=True)
class Estate:
    """The repositories to sweep and the counts of those left out."""

    names: tuple[str, ...]
    excluded: Excluded


def classify_repositories(
    rows: list[dict[str, typ.Any]],
    hidden_private: int | None = None,
) -> Estate:
    """Split a repository listing into the swept set and exclusion counts.

    Parameters
    ----------
    rows
        Listing rows with `name`, `isFork`, `isArchived` and `visibility`.
    hidden_private
        How many private repositories exist but are invisible to the caller's
        token (a CI token sees only public ones). Used only when the listing
        shows none.

    Returns
    -------
    Estate
        Sorted public, active, non-fork names; counts of forks and archived
        public repositories; and the private count (None when unknown).

    Examples
    --------
    >>> row = {"name": "a", "isFork": False, "isArchived": False}
    >>> rows = [{**row, "visibility": "PUBLIC"}]
    >>> classify_repositories(rows).names
    ('a',)
    """
    public = [row for row in rows if row["visibility"] == PUBLIC]
    private = len(rows) - len(public)
    swept = [r for r in public if not r["isFork"] and not r["isArchived"]]
    excluded = Excluded(
        forks=sum(1 for r in public if r["isFork"]),
        archived=sum(1 for r in public if r["isArchived"] and not r["isFork"]),
        private=private or hidden_private,
    )
    return Estate(tuple(sorted(r["name"] for r in swept)), excluded)


def list_estate(owner: str, hidden_private: int | None = None) -> Estate:
    """Ask GitHub for *owner*'s repositories and classify them.

    One GraphQL-backed listing call; no per-repository API reads.

    Parameters
    ----------
    owner
        The GitHub user or organisation.
    hidden_private
        See `classify_repositories`.

    Returns
    -------
    Estate
        The swept names and exclusion counts.
    """
    raw = gh("repo", "list", owner, "--limit", LIST_LIMIT, "--json", LIST_FIELDS)
    return classify_repositories(json.loads(raw), hidden_private)
