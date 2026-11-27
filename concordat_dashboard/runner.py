"""Adapt concordat's in-process rule runner to the sweep.

This mirrors what `concordat artefact rule run` composes: action pins resolved
through a disk cache, and Whitaker revisions certified through GitHub. The
difference is that one certifier serves every repository the process sweeps,
so the same shared-actions question is asked once, not once per repository.
"""

import functools
import importlib.metadata
import json
import logging
import os
import sys
import typing as typ

from concordat.auditor.github import GithubClient
from concordat.errors import OperationalRuleError
from concordat.rules import run_rule
from concordat.rules.github_pins import GithubPinResolver
from concordat.rules.github_whitaker_certification import (
    GithubCertifier,
    github_certifier,
)
from concordat.rules.packages import (
    default_envelope_builder,
    resolving_pins,
    rule_package_dir,
    rule_parameters,
)
from concordat.rules.pin_cache import PinCache, cached_resolver
from concordat.rules.provisioning_certification import certifying

from .catalogue import PLACEMENTS
from .classify import RawFinding
from .process import CommandFailedError, gh

if typ.TYPE_CHECKING:
    import collections.abc as cabc
    import pathlib

LOG = logging.getLogger(__name__)
API_URL = "https://api.github.com"
INDETERMINATE = "indeterminate"
UNKNOWN_COMMIT = "unknown"


def github_token() -> str | None:
    """Return a GitHub token from the environment, else from the `gh` login.

    Returns
    -------
    str | None
        The token, or None when neither source has one (rules that need the
        API then report indeterminate).
    """
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    try:
        found = gh("auth", "token").strip() or None
    except CommandFailedError, OSError:
        # No `gh` login, or no `gh` at all: the rules degrade to indeterminate.
        found = None
    if found is None:
        warn_unauthenticated()
    return found


def warn_unauthenticated() -> None:
    """Announce, as a workflow annotation, that no token could be found.

    A quota-starved sweep must be visible in the run, not only on the page.
    """
    sys.stderr.write(
        "::warning title=No GitHub token::no token in GITHUB_TOKEN, GH_TOKEN or"
        " the gh login; rules that need the API report indeterminate\n"
    )


def concordat_identity() -> tuple[str, str]:
    """Report the installed concordat's version and the commit it was pinned to.

    Returns
    -------
    tuple[str, str]
        The package version and the full commit SHA ("unknown" when concordat
        was not installed from a git reference).
    """
    dist = importlib.metadata.distribution("concordat")
    raw = dist.read_text("direct_url.json") or "{}"
    commit = json.loads(raw).get("vcs_info", {}).get("commit_id", UNKNOWN_COMMIT)
    return dist.version, commit


def rule_defaults(rule_id: str) -> cabc.Mapping[str, object]:
    """Return a package's manifest parameter defaults (where exemptions live).

    Parameters
    ----------
    rule_id
        The rule package id.

    Returns
    -------
    cabc.Mapping[str, object]
        The defaults; empty when the package declares none.
    """
    return rule_parameters(rule_package_dir(rule_id))


def packages_root() -> pathlib.Path:
    """Return the directory holding the installed concordat's rule packages.

    Returns
    -------
    pathlib.Path
        The parent of every rule package directory.

    Notes
    -----
    Any one declared package being absent is tolerated, because main may drop a
    rule and that must not stop publication. Only when concordat ships none of
    them is the last `OperationalRuleError` re-raised.
    """
    errors: list[OperationalRuleError] = []
    for rule_id in PLACEMENTS:
        try:
            return rule_package_dir(rule_id).parent
        except OperationalRuleError as error:
            errors.append(error)
    raise errors[-1]


class Runner:
    """Run rule packages against checkouts with a shared pin cache and certifier."""

    def __init__(self, pin_cache_dir: pathlib.Path, token: str | None) -> None:
        """Build the resolver chain once for every rule this runner runs."""
        self._client = functools.partial(GithubClient, token=token, api_url=API_URL)
        self._certifier: GithubCertifier | None = None
        resolver = cached_resolver(
            GithubPinResolver(self._client), PinCache(pin_cache_dir, API_URL)
        )
        self._builder = certifying(
            resolving_pins(default_envelope_builder, resolver),
            self._shared_certifier,
        )

    def _shared_certifier(
        self, parameters: cabc.Mapping[str, object]
    ) -> GithubCertifier:
        """Return the one certifier every repository shares.

        Returns
        -------
        GithubCertifier
            The shared certifier.

        Certification depends only on the shared-actions revision, so its
        answers are memoized inside the certifier and reused across repositories.
        """
        if self._certifier is None:
            self._certifier = github_certifier(self._client, parameters)
        return self._certifier

    def run(self, rule_id: str, tree: pathlib.Path) -> tuple[RawFinding, ...]:
        """Run one rule against one checkout.

        Parameters
        ----------
        rule_id
            The rule package id.
        tree
            The checkout to audit.

        Returns
        -------
        tuple[RawFinding, ...]
            Every finding; an operational failure comes back as a single
            indeterminate finding carrying the reason, so one broken rule
            cannot fail the sweep.
        """
        try:
            result = run_rule(rule_id, tree, envelope_builder=self._builder)
        except Exception as error:  # ruff: ignore[blind-except] - any rule failure becomes one cell's reason
            # Only the exception class is published; its message could carry
            # anything a rule read.
            reason = f"the rule could not run ({type(error).__name__})"
            LOG.warning("%s: %s", rule_id, reason)
            return (RawFinding("ERROR", "", 0, reason, is_indeterminate=True),)
        return tuple(
            RawFinding(f.rule_id, f.path, f.line, f.message, f.verdict == INDETERMINATE)
            for f in result.findings
        )
