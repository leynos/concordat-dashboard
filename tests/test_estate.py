"""Only public, active, non-fork repositories are swept; private ones are counted."""

import json
import typing as typ

import pytest

from concordat_dashboard import estate as estate_module
from concordat_dashboard.estate import (
    IncompleteListingError,
    classify_repositories,
    list_estate,
)

if typ.TYPE_CHECKING:
    import collections.abc as cabc

    from concordat_dashboard.estate import Estate


def _row(
    name: str, *, visibility: str = "PUBLIC", flags: tuple[str, ...] = ()
) -> dict[str, typ.Any]:
    """Build one listing row; *flags* may name `fork`, `archived` and `empty`.

    Returns
    -------
    dict[str, typ.Any]
        The row as `gh repo list --json` prints it.
    """
    return {
        "name": name,
        "isFork": "fork" in flags,
        "isArchived": "archived" in flags,
        "isEmpty": "empty" in flags,
        "visibility": visibility,
    }


ROWS = [
    _row("zeta"),
    _row("alpha"),
    _row("a-fork", flags=("fork",)),
    _row("old", flags=("archived",)),
    _row("forked-and-archived", flags=("fork", "archived")),
    _row("secret", visibility="PRIVATE"),
    _row("secret-archived", visibility="PRIVATE", flags=("archived",)),
    _row("no-commits", flags=("empty",)),
]


def test_swept_names_are_public_active_non_forks_in_order() -> None:
    """The swept set is filtered and sorted."""
    names = classify_repositories(ROWS).names
    assert names == ("alpha", "zeta"), "only public active non-forks, sorted"


def test_exclusions_are_counted_without_double_counting() -> None:
    """A fork that is also archived counts as a fork only."""
    excluded = classify_repositories(ROWS).excluded
    counts = (excluded.forks, excluded.archived, excluded.private, excluded.empty)
    assert counts == (2, 1, 2, 1), "forks, archived, private and empty counts"


def test_private_names_never_reach_the_estate() -> None:
    """A private repository's name must not appear anywhere in the result."""
    estate = classify_repositories(ROWS)
    assert "secret" not in repr(estate), "a private name leaked into the estate"


def test_invisible_private_repositories_use_the_supplied_count() -> None:
    """A CI token sees no private rows, so the configured count is used."""
    estate = classify_repositories([_row("alpha")], hidden_private=11)
    assert estate.excluded.private == 11, "the supplied count must be used"


def test_unknown_private_count_stays_unknown() -> None:
    """With no private rows and no supplied count, the page prints no count."""
    estate = classify_repositories([_row("alpha")])
    assert estate.excluded.private is None, "an unknown count must stay None"


def test_visible_private_rows_win_over_the_supplied_count() -> None:
    """What the listing shows is more trustworthy than a configured number."""
    rows = [_row("alpha"), _row("hidden", visibility="PRIVATE")]
    estate = classify_repositories(rows, hidden_private=99)
    assert estate.excluded.private == 1, "the listing's own count must win"


@pytest.fixture
def listing(monkeypatch: pytest.MonkeyPatch) -> cabc.Callable[[int], Estate]:
    """Provide a function that lists *n* repositories under a cap of three.

    Returns
    -------
    cabc.Callable[[int], Estate]
        Takes the number of repositories GitHub returns; returns the estate.
    """
    monkeypatch.setattr(estate_module, "LIST_LIMIT", 3)

    def list_n(count: int) -> Estate:
        """List *count* repositories through the stubbed `gh`.

        Returns
        -------
        Estate
            The classified listing.
        """
        rows = [_row(f"r{i}") for i in range(count)]
        monkeypatch.setattr(estate_module, "gh", lambda *_args: json.dumps(rows))
        return list_estate("leynos")

    return list_n


def test_listing_that_reaches_the_cap_is_rejected(
    listing: cabc.Callable[[int], Estate],
) -> None:
    """A truncated listing must not be published as complete coverage."""
    with pytest.raises(IncompleteListingError, match="limit"):
        listing(3)


def test_listing_below_the_cap_passes_through(
    listing: cabc.Callable[[int], Estate],
) -> None:
    """A listing under the cap is classified."""
    assert len(listing(2).names) == 2, "names pass through"
