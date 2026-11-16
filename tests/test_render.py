"""The rendered pages carry every state, the finding text and the exclusions."""

import dataclasses
import typing as typ

import pytest

from concordat_dashboard.model import Excluded, Sweep
from concordat_dashboard.render import render_index, write_site

if typ.TYPE_CHECKING:
    import pathlib


def _missing(page: str, expected: tuple[str, ...]) -> list[str]:
    """List the expected fragments a page does not contain.

    Returns
    -------
    list[str]
        The absent fragments; empty when all are present.
    """
    return [fragment for fragment in expected if fragment not in page]


def test_index_names_every_repository_and_rule(sweep: Sweep) -> None:
    """Rows and columns are all present and rows link to their detail pages."""
    html = render_index(sweep)
    expected = tuple(f'href="repos/{r.name}.html"' for r in sweep.repos)
    expected += tuple(rule.id for rule in sweep.rules)
    assert not _missing(html, expected), "a repository or rule is missing"


def test_every_state_has_words_for_screen_readers(sweep: Sweep) -> None:
    """No mark depends on colour or glyph alone."""
    html = render_index(sweep)
    words = (
        "non-compliant, 2 findings",
        "indeterminate",
        "exempt",
        "not applicable",
        "compliant",
    )
    expected = tuple(f'<span class="sr-only">{w}</span>' for w in words)
    assert not _missing(html, expected), "a state has no screen-reader text"


def test_compliant_is_never_drawn_as_a_cross(sweep: Sweep) -> None:
    """The most common mark must not read as failure."""
    html = render_index(sweep)
    assert "\N{MULTIPLICATION SIGN}" not in html, "a cross glyph is on the page"
    assert "&times;" not in html, "a cross entity is on the page"


def test_index_records_concordat_commit_and_head_shas(sweep: Sweep) -> None:
    """Provenance is on the page."""
    html = render_index(sweep)
    expected = ("e9d254f4439e", "a" * 7, "b" * 7)
    assert not _missing(html, expected), "provenance is missing from the page"


def test_private_count_is_one_line_and_names_nothing(sweep: Sweep) -> None:
    """The count shows; no private name can, because none is in the model."""
    html = render_index(sweep)
    assert "11 private repositories not shown" in html, "the private count is shown"


def test_unknown_private_count_prints_no_line(sweep: Sweep) -> None:
    """With no count to give, the page says nothing about private repositories."""
    unknown = dataclasses.replace(sweep, excluded=Excluded(21, 6, None))
    assert "private" not in render_index(unknown), "no count means no line"


@pytest.fixture
def site(sweep: Sweep, tmp_path: pathlib.Path) -> pathlib.Path:
    """Write the sample sweep's site.

    Returns
    -------
    pathlib.Path
        The site directory.
    """
    write_site(sweep, tmp_path)
    return tmp_path


def test_finding_text_is_escaped(site: pathlib.Path) -> None:
    """A finding message is data, not markup."""
    page = (site / "repos" / "rusty.html").read_text("utf-8")
    assert "&lt;groups&gt;" in page, "the message must be escaped"
    assert "<groups>" not in page, "the message must not become markup"


def test_site_has_one_page_per_repository_with_rule_anchors(
    site: pathlib.Path,
) -> None:
    """Cells link to `repos/<name>.html#<rule>`, so each rule needs an anchor."""
    page = (site / "repos" / "rusty.html").read_text("utf-8")
    expected = (
        'id="rust-makefile-baseline"',
        "gate reachability cannot be proven",
        "Compiles one file with rustc.",
    )
    index = (site / "index.html").read_text("utf-8")
    assert len(list(site.rglob("*.html"))) == 3, "an index and one page per repository"
    assert not _missing(page, expected), "the detail page lacks a section or text"
    assert 'href="repos/rusty.html#dependabot-update-shape"' in index, "cell link"


def test_rendering_again_removes_pages_of_repositories_that_left(
    sweep: Sweep, site: pathlib.Path
) -> None:
    """A repository that left the sweep must not stay reachable by name."""
    remaining = dataclasses.replace(sweep, repos=sweep.repos[:1])
    write_site(remaining, site)
    names = sorted(p.name for p in (site / "repos").glob("*.html"))
    assert names == ["plain.html"], "the page of the repository that left is gone"


def test_pages_load_no_remote_script_or_stylesheet(site: pathlib.Path) -> None:
    """The published page is static: no CDN."""
    html = (site / "index.html").read_text("utf-8")
    detail = (site / "repos" / "plain.html").read_text("utf-8")
    assert "<script" not in html, "the page must load no script"
    assert 'href="coupon.css"' in html, "the index uses its local stylesheet"
    assert 'href="../coupon.css"' in detail, "detail pages use the same stylesheet"
