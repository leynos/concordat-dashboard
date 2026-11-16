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
LIST_FIELDS = "name,isFork,isArchived,isEmpty,visibility"
LIST_LIMIT = 1000


class IncompleteListingError(RuntimeError):
    """The repository listing may be truncated, so coverage would be partial."""


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
        Sorted public, active, non-fork, non-empty names; counts of forks,
        archived and empty public repositories; and the private count (None
        when unknown).

    Examples
    --------
    >>> row = {"name": "a", "isFork": False, "isArchived": False}
    >>> rows = [{**row, "visibility": "PUBLIC"}]
    >>> classify_repositories(rows).names
    ('a',)
    """
    public = [row for row in rows if row["visibility"] == PUBLIC]
    private = len(rows) - len(public)
    active = [r for r in public if not r["isFork"] and not r["isArchived"]]
    # A repository with no commits has no default branch to fetch.
    swept = [r for r in active if not r.get("isEmpty", False)]
    excluded = Excluded(
        forks=sum(1 for r in public if r["isFork"]),
        archived=sum(1 for r in public if r["isArchived"] and not r["isFork"]),
        private=private or hidden_private,
        empty=len(active) - len(swept),
    )
    return Estate(tuple(sorted(r["name"] for r in swept)), excluded)


def list_estate(owner: str, hidden_private: int | None = None) -> Estate:
    """Ask GitHub for *owner*'s repositories and classify them.

    One GraphQL-backed listing call; no per-repository API reads.

    Parameters
    ----------
    owner
        The GitHub user or organization.
    hidden_private
        See `classify_repositories`.

    Returns
    -------
    Estate
        The swept names and exclusion counts.

    Raises
    ------
    IncompleteListingError
        If the listing reached the request limit, so repositories may be missing.
    """
    raw = gh("repo", "list", owner, "--limit", str(LIST_LIMIT), "--json", LIST_FIELDS)
    rows = json.loads(raw)
    if len(rows) >= LIST_LIMIT:
        message = f"the listing reached its limit of {LIST_LIMIT}; raise LIST_LIMIT"
        raise IncompleteListingError(message)
    return classify_repositories(rows, hidden_private)
