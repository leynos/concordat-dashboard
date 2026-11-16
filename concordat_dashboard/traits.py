"""Detect the repository properties a rule's applicability depends on.

Detection reads file names and, for uv, a few build files; it never runs
anything. It only decides whether a *compliant* verdict reads as "not
applicable": a finding from a rule always wins over a missing trait.
"""

import os
import pathlib
import re

from .model import Trait

# Trees that hold somebody else's code or generated output.
SKIPPED_DIRECTORIES = frozenset({
    ".git",
    "node_modules",
    "vendor",
    "target",
    ".venv",
    "third_party",
})
UV_MENTION = re.compile(r"\buvx?\b")


def _owned_files(tree: pathlib.Path) -> list[pathlib.Path]:
    """List the files a repository owns, skipping vendored and generated trees.

    Returns
    -------
    list[pathlib.Path]
        The owned files.
    """
    owned: list[pathlib.Path] = []
    for directory, subdirectories, names in os.walk(tree):
        subdirectories[:] = [d for d in subdirectories if d not in SKIPPED_DIRECTORIES]
        owned.extend(pathlib.Path(directory, name) for name in names)
    return owned


def _mentions_uv(tree: pathlib.Path) -> bool:
    """Report whether the Makefile or a workflow runs uv.

    Returns
    -------
    bool
        True when either mentions `uv` or `uvx`.
    """
    candidates = [tree / "Makefile", *(tree / ".github").glob("**/*.y*ml")]
    return any(
        UV_MENTION.search(path.read_text("utf-8", errors="replace"))
        for path in candidates
        if path.is_file()
    )


def detect_traits(tree: pathlib.Path) -> frozenset[Trait]:
    """Work out which languages and tools a checkout uses.

    Parameters
    ----------
    tree
        The checkout to inspect.

    Returns
    -------
    frozenset[Trait]
        `RUST` for any owned `.rs` file, `PYTHON` for any owned `.py` file or
        a `pyproject.toml`, and `UV` for a `pyproject.toml`, a `uv.lock`, or a
        Makefile or workflow that runs `uv`.

    Examples
    --------
    >>> import pathlib, tempfile
    >>> with tempfile.TemporaryDirectory() as raw:
    ...     _ = pathlib.Path(raw, "lib.rs").write_text("")
    ...     sorted(detect_traits(pathlib.Path(raw)))
    [<Trait.RUST: 'rust'>]
    """
    files = _owned_files(tree)
    names = {path.name for path in files}
    suffixes = {path.suffix for path in files}
    found: set[Trait] = set()
    if ".rs" in suffixes:
        found.add(Trait.RUST)
    if ".py" in suffixes or "pyproject.toml" in names:
        found.add(Trait.PYTHON)
    if {"pyproject.toml", "uv.lock"} & names or _mentions_uv(tree):
        found.add(Trait.UV)
    return frozenset(found)
