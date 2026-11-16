"""Run the two external programs the sweep needs, through cuprum's allowlist."""

import typing as typ

from cuprum import Program, ProgramCatalogue, ProjectSettings, sh

if typ.TYPE_CHECKING:
    import pathlib

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
    """A command exited non-zero."""


def _run(program: Program, args: tuple[str, ...]) -> str:
    """Run *program* with *args* and return its standard output.

    Returns
    -------
    str
        Standard output.

    Raises
    ------
    CommandFailedError
        If the program exits non-zero.
    """
    result = sh.make(program, catalogue=_CATALOGUE)(*args).run_sync()
    if not result.ok:
        # cuprum 0.1.0 types the streams as optional; they are captured here.
        detail = (result.stderr or "").strip()[-300:]
        message = (
            f"{program} {' '.join(args[:3])} failed ({result.exit_code}): {detail}"
        )
        raise CommandFailedError(message)
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
