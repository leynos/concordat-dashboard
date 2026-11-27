"""The runner turns concordat's results, and its failures, into raw findings."""

import shutil
import types
import typing as typ

import pytest

from concordat_dashboard import runner as runner_module
from concordat_dashboard.runner import Runner, concordat_identity

if typ.TYPE_CHECKING:
    import pathlib


def test_operational_failure_becomes_one_indeterminate_finding(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A rule that cannot run must not fail the sweep."""

    def explode(*_args: object, **_kwargs: object) -> None:
        """Fail as a missing Conftest would.

        Raises
        ------
        RuntimeError
            Always.
        """
        message = "conftest is not installed for leynos/a-private-repository"
        raise RuntimeError(message)

    monkeypatch.setattr(runner_module, "run_rule", explode)
    with caplog.at_level("WARNING"):
        findings = Runner(tmp_path / "pins", None).run("yaml-lint-baseline", tmp_path)
    assert len(findings) == 1, "one failure is one finding"
    assert findings[0].is_indeterminate, "a failure is never a breach"
    assert "RuntimeError" in findings[0].message, "the kind of failure is kept"
    assert "private" not in findings[0].message, "the exception text is not published"
    assert "yaml-lint-baseline" in caplog.text, "the failed rule is logged"
    assert "private" not in caplog.text, "the exception text is not logged either"


def test_a_missing_gh_binary_means_no_token_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without `gh` the rules that need the API degrade; the sweep still runs."""

    def no_gh(*_args: str) -> str:
        """Fail as a missing executable does.

        Raises
        ------
        FileNotFoundError
            Always.
        """
        raise FileNotFoundError

    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(runner_module, "gh", no_gh)
    assert runner_module.github_token() is None, "no token, no crash"


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        ({"GITHUB_TOKEN": "a", "GH_TOKEN": "b"}, "a"),
        ({"GH_TOKEN": "b"}, "b"),
        ({}, "from-gh-login"),
    ],
)
def test_token_precedence(
    monkeypatch: pytest.MonkeyPatch, environment: dict[str, str], expected: str
) -> None:
    """GITHUB_TOKEN, then GH_TOKEN, then the `gh` login."""
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(runner_module, "gh", lambda *_args: "from-gh-login\n")
    assert runner_module.github_token() == expected, "token precedence"


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


@pytest.mark.parametrize(
    "direct_url",
    [None, "{}", '{"url": "file:///somewhere"}'],
    ids=["no-file", "empty", "not-vcs"],
)
def test_concordat_identity_without_a_git_commit_is_unknown(
    monkeypatch: pytest.MonkeyPatch, direct_url: str | None
) -> None:
    """A concordat not installed from git has no commit to claim."""
    # `direct_url` is None when the distribution has no `direct_url.json`.
    dist = types.SimpleNamespace(version="9.9.9", read_text=lambda _n: direct_url)
    monkeypatch.setattr(
        runner_module.importlib.metadata, "distribution", lambda _name: dist
    )
    assert concordat_identity() == ("9.9.9", runner_module.UNKNOWN_COMMIT), "unknown"


def test_the_packages_root_survives_one_rule_being_dropped(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Concordat dropping one rule must not stop the root being found."""
    real = runner_module.rule_package_dir

    def drop_yaml_lint(rule_id: str) -> pathlib.Path:
        """Resolve packages as concordat does, except the one dropped.

        Returns
        -------
        pathlib.Path
            The package directory.

        Raises
        ------
        OperationalRuleError
            For `yaml-lint-baseline`, as if it were absent.
        """
        if rule_id == "yaml-lint-baseline":
            message = "unknown rule package 'yaml-lint-baseline'"
            raise runner_module.OperationalRuleError(
                message, operation="load-rule-package"
            )
        return real(rule_id)

    monkeypatch.setattr(runner_module, "rule_package_dir", drop_yaml_lint)
    assert runner_module.packages_root() == real("uv-gate-baseline").parent, "root"


def test_a_missing_token_is_announced_as_a_workflow_warning(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No token must not pass silently: the run shows a `::warning`."""
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(runner_module, "gh", lambda *_args: "\n")
    found = runner_module.github_token()
    assert found is None, "an empty login is no token"
    assert capsys.readouterr().err.startswith("::warning"), "the annotation is raised"


def test_a_found_token_raises_no_warning(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An authenticated run stays quiet."""
    monkeypatch.setenv("GITHUB_TOKEN", "a")
    assert runner_module.github_token() == "a", "the environment token is used"
    assert not capsys.readouterr().err, "nothing is announced"
