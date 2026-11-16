"""Run the two external programs the sweep needs, through cuprum's allowlist."""

import asyncio
import typing as typ

from cuprum import Program, ProgramCatalogue, ProjectSettings, sh

if typ.TYPE_CHECKING:
    import pathlib

# A shallow fetch or a repository listing takes seconds; this only bounds a
# stalled connection so one repository cannot hold the whole sweep.
DEADLINE_SECONDS = 300.0
GIT = Program("git")
GH = Program("gh")
# cuprum 0.1.0 builds a catalogue from project settings, not `from_programs`.
_CATALOGUE = ProgramCatalogue(
    projects=[
        ProjectSettings(
            name="concordat-dashboard",
            programs=(GIT, GH),
            documentation_locations=(),
            noise_rules=(),
        )
    ]
)


class CommandFailedError(RuntimeError):
    """A command failed.

    The message may carry the command's standard error, which can name things
    that must not be published. `public_summary` is the part safe to show: the
    program, its first arguments and how it failed, never its output.
    """

    def __init__(self, message: str, public_summary: str = "a command failed") -> None:
        """Keep the full *message* and the publishable *public_summary*."""
        super().__init__(message)
        self.public_summary = public_summary


def _run(program: Program, args: tuple[str, ...]) -> str:
    """Run *program* with *args* and return its standard output.

    Returns
    -------
    str
        Standard output.

    Raises
    ------
    CommandFailedError
        If the program exits non-zero or outlives `DEADLINE_SECONDS`.
    """
    command = sh.make(program, catalogue=_CATALOGUE)(*args)
    try:
        # cuprum 0.1.0's synchronous run has no deadline; cancelling the async
        # run reaches its child-termination path.
        result = asyncio.run(asyncio.wait_for(command.run(), DEADLINE_SECONDS))
    except TimeoutError as error:
        # No arguments in the summary: they can hold a checkout path.
        summary = f"{program} timed out after {DEADLINE_SECONDS:g}s"
        raise CommandFailedError(summary, summary) from error
    if not result.ok:
        # cuprum 0.1.0 types the streams as optional; they are captured here.
        detail = (result.stderr or "").strip()[-300:]
        summary = f"{program} failed ({result.exit_code})"
        message = f"{summary}: {detail}"
        raise CommandFailedError(message, summary)
    return result.stdout or ""


def git(*args: str) -> str:
    """Run git and return its standard output.

    Parameters
    ----------
    *args
        The git arguments; there is no shell, so none are interpreted.

    Returns
    -------
    str
        Standard output; a non-zero exit raises `CommandFailedError`.

    Examples
    --------
    >>> git("--version").startswith("git version")
    True
    """
    return _run(GIT, args)


def gh(*args: str) -> str:
    """Run the GitHub CLI and return its standard output.

    Parameters
    ----------
    *args
        The `gh` arguments.

    Returns
    -------
    str
        Standard output; a non-zero exit raises `CommandFailedError`.
    """
    return _run(GH, args)


def git_in(directory: pathlib.Path, *args: str) -> str:
    """Run git inside *directory* and return its standard output.

    Parameters
    ----------
    directory
        The repository to run in.
    *args
        The git arguments.

    Returns
    -------
    str
        Standard output.
    """
    return git("-C", str(directory), *args)
