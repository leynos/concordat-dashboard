"""Render the coupon and the per-repository pages with Jinja."""

import dataclasses
import datetime as dt
import pathlib
import typing as typ

import jinja2

from .detail import page_of
from .view import RESULT_LABELS, RESULT_TITLES, coupon_of

if typ.TYPE_CHECKING:
    from .model import Sweep

TEMPLATES = pathlib.Path(__file__).parent / "templates"
SOURCE_NAME = "leynos/concordat-dashboard"
SOURCE_URL = "https://github.com/leynos/concordat-dashboard"


@dataclasses.dataclass(frozen=True, slots=True)
class Page:
    """The facts every page's masthead and footer print."""

    owner: str
    root: str
    generated_iso: str
    date_long: str
    date_short: str
    concordat_version: str
    concordat_commit: str
    source_url: str = SOURCE_URL
    source_name: str = SOURCE_NAME


def environment() -> jinja2.Environment:
    """Build the Jinja environment: autoescaped, and strict about missing names.

    Returns
    -------
    jinja2.Environment
        The environment that loads the packaged templates.
    """
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
    )


def page_for(sweep: Sweep, root: str) -> Page:
    """Build the masthead facts for a page.

    Parameters
    ----------
    sweep
        The sweep being published.
    root
        The relative path from the page back to the site root: `""` or `"../"`.

    Returns
    -------
    Page
        The facts.
    """
    when = dt.datetime.fromisoformat(sweep.generated_at)
    return Page(
        owner=sweep.owner,
        root=root,
        generated_iso=sweep.generated_at,
        date_long=f"{when.day} {when:%B %Y}",
        date_short=f"{when:%d.%m.%y}",
        concordat_version=sweep.concordat_version,
        concordat_commit=sweep.concordat_commit,
    )


def render_index(sweep: Sweep) -> str:
    """Render the coupon page.

    Parameters
    ----------
    sweep
        The sweep to publish.

    Returns
    -------
    str
        The HTML document.
    """
    return (
        environment()
        .get_template("coupon.html.j2")
        .render(
            page=page_for(sweep, ""),
            coupon=coupon_of(sweep),
            excluded=sweep.excluded,
            result_labels=RESULT_LABELS,
            result_titles=RESULT_TITLES,
        )
    )


def write_site(sweep: Sweep, out: pathlib.Path) -> int:
    """Write `index.html` and one `repos/<name>.html` per repository.

    A repository page left over from an earlier render is deleted: a repository
    that has since left the sweep (for example, made private) must not stay
    reachable by name.

    Parameters
    ----------
    sweep
        The sweep to publish.
    out
        The site directory; created if absent. The stylesheet and fonts are
        added by the build, not here.

    Returns
    -------
    int
        The number of pages written.
    """
    pages = out / "repos"
    pages.mkdir(parents=True, exist_ok=True)
    current = {f"{repo.name}.html" for repo in sweep.repos}
    for stale in (p for p in pages.glob("*.html") if p.name not in current):
        stale.unlink()
    (out / "index.html").write_text(render_index(sweep), "utf-8")
    template = environment().get_template("repo.html.j2")
    for repo in sweep.repos:
        html = template.render(page=page_for(sweep, "../"), repo=page_of(repo, sweep))
        (pages / f"{repo.name}.html").write_text(html, "utf-8")
    return len(sweep.repos) + 1
