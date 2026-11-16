"""External commands run through the allowlist and are bounded by a deadline."""

import typing as typ

import pytest
from cuprum import Program, ProgramCatalogue, ProjectSettings

from concordat_dashboard import process
from concordat_dashboard.process import CommandFailedError, git, git_in

if typ.TYPE_CHECKING:
    import pathlib

SLEEP = Program("sleep")


def test_non_zero_exit_raises_with_the_reason() -> None:
    """A failing command is an error carrying git's own message."""
    with pytest.raises(CommandFailedError, match="failed"):
        git("rev-parse", "--verify", "--quiet", "no-such-ref-anywhere")


def test_public_summary_carries_no_arguments_or_output(
    tmp_path: pathlib.Path,
) -> None:
    """A checkout path in the arguments must not reach the publishable summary."""
    private_dir = tmp_path / "a-private-repository"
    with pytest.raises(CommandFailedError) as caught:
        git_in(private_dir, "rev-parse", "HEAD")
    assert caught.value.public_summary == "git failed (128)", "program and exit code"
    assert "a-private-repository" not in caught.value.public_summary, "no path"


def test_stalled_command_is_cut_off_at_the_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hung fetch must become a reportable failure, not a stuck sweep."""
    catalogue = ProgramCatalogue(
        projects=[
            ProjectSettings(
                name="test",
                programs=(SLEEP,),
                documentation_locations=(),
                noise_rules=(),
            )
        ]
    )
    monkeypatch.setattr(process, "GIT", SLEEP)
    monkeypatch.setattr(process, "_CATALOGUE", catalogue)
    monkeypatch.setattr(process, "DEADLINE_SECONDS", 0.5)
    with pytest.raises(CommandFailedError, match="timed out"):
        git("30")
