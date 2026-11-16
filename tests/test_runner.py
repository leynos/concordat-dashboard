"""The runner turns concordat's results, and its failures, into raw findings."""

import shutil
import typing as typ

import pytest

from concordat_dashboard import runner as runner_module
from concordat_dashboard.runner import Runner, concordat_identity

if typ.TYPE_CHECKING:
    import pathlib


def test_operational_failure_becomes_one_indeterminate_finding(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rule that cannot run must not fail the sweep."""

    def explode(*_args: object, **_kwargs: object) -> None:
        """Fail as a missing Conftest would.

        Raises
        ------
        RuntimeError
            Always.
        """
        message = "conftest is not installed"
        raise RuntimeError(message)

    monkeypatch.setattr(runner_module, "run_rule", explode)
    findings = Runner(tmp_path / "pins", None).run("yaml-lint-baseline", tmp_path)
    assert len(findings) == 1, "one failure is one finding"
    assert findings[0].is_indeterminate, "a failure is never a breach"
    assert "conftest is not installed" in findings[0].message, "the reason is kept"


@pytest.mark.skipif(
    shutil.which("conftest") is None, reason="conftest is not installed"
)
def test_real_rule_runs_on_an_empty_tree(tmp_path: pathlib.Path) -> None:
    """The in-process path reaches Conftest; an empty tree has no Dependabot file."""
    tree = tmp_path / "tree"
    tree.mkdir()
    findings = Runner(tmp_path / "pins", None).run("dependabot-update-shape", tree)
    assert len(findings) == 0, "a repository with no Dependabot file is compliant"


def test_concordat_identity_reports_the_pinned_commit() -> None:
    """The page prints the commit the dependency was pinned to."""
    version, commit = concordat_identity()
    assert version, "concordat has a version"
    assert len(commit) == 40, "the pinned commit is a full SHA"
