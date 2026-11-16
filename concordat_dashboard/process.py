"""Run the two external programs the sweep needs, through cuprum's allowlist."""

import asyncio
import threading
import typing as typ

from cuprum import Program, ProgramCatalogue, ProjectSettings, sh

if typ.TYPE_CHECKING:
    import pathlib

    from cuprum import CommandResult, SafeCmd

# A shallow fetch or a repository listing takes seconds; this only bounds a
# stalled connection so one repository cannot hold the whole sweep.
DEADLINE_SECONDS = 300.0
# How long cleanup after the deadline may take before the call is abandoned.
CLEANUP_GRACE_SECONDS = 15.0
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
    program and how it failed (exit code or timeout), never its arguments, which
    can hold a checkout path, and never its output.
    """

    def __init__(self, message: str, public_summary: str = "a command failed") -> None:
        """Keep the full *message* and the publishable *public_summary*."""
        super().__init__(message)
        self.public_summary = public_summary


def _run_bounded(command: SafeCmd) -> CommandResult:
    """Run *command* on a helper thread and give up after the deadline plus grace.

    Cancelling the async run stops the direct child, but cuprum then waits for
    its output pipes to close, and a descendant (such as `git-remote-https`)
    that inherited them can hold them open indefinitely. Joining the thread
    with a limit bounds the whole call whatever the descendant does; a thread
    that is still stuck is abandoned (it is a daemon, so it cannot keep the
    process alive).

    Returns
    -------
    CommandResult
        The command's result.

    Raises
    ------
    TimeoutError
        If the command and its cleanup outlive the limit.
    """
    outcome: dict[str, typ.Any] = {}

    def target() -> None:
        """Run the command, recording its result or the error it raised."""
        try:
            outcome["result"] = asyncio.run(
                asyncio.wait_for(command.run(), DEADLINE_SECONDS)
            )
        except BaseException as error:  # ruff: ignore[blind-except] - handed to the caller
            outcome["error"] = error

    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    worker.join(DEADLINE_SECONDS + CLEANUP_GRACE_SECONDS)
    if worker.is_alive():
        message = "the command's cleanup did not finish"
        raise TimeoutError(message)
    if "error" in outcome:
        raise outcome["error"]
    return outcome["result"]


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
        result = _run_bounded(command)
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
