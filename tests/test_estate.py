"""Only public, active, non-fork repositories are swept; private ones are counted."""

import typing as typ

from concordat_dashboard.estate import classify_repositories


def _row(
    name: str, *, visibility: str = "PUBLIC", fork: bool = False, archived: bool = False
) -> dict[str, typ.Any]:
    """Build one listing row.

    Returns
    -------
    dict[str, typ.Any]
        The row as `gh repo list --json` prints it.
    """
    return {
        "name": name,
        "isFork": fork,
        "isArchived": archived,
        "visibility": visibility,
    }


ROWS = [
    _row("zeta"),
    _row("alpha"),
    _row("a-fork", fork=True),
    _row("old", archived=True),
    _row("forked-and-archived", fork=True, archived=True),
    _row("secret", visibility="PRIVATE"),
    _row("secret-archived", visibility="PRIVATE", archived=True),
]


def test_swept_names_are_public_active_non_forks_in_order() -> None:
    """The swept set is filtered and sorted."""
    names = classify_repositories(ROWS).names
    assert names == ("alpha", "zeta"), "only public active non-forks, sorted"


def test_exclusions_are_counted_without_double_counting() -> None:
    """A fork that is also archived counts as a fork only."""
    excluded = classify_repositories(ROWS).excluded
    counts = (excluded.forks, excluded.archived, excluded.private)
    assert counts == (2, 1, 2), "forks, archived and private counts"


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
