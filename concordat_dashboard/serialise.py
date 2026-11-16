"""Read and write the sweep as JSON, so `sweep` and `render` can run apart."""

import json
import typing as typ

from .model import (
    Cell,
    Excluded,
    Exemption,
    Finding,
    RepoResult,
    RuleInfo,
    State,
    Sweep,
    Trait,
)

type Json = dict[str, typ.Any]


def _cell_from_json(raw: Json) -> Cell:
    """Rebuild one cell.

    Returns
    -------
    Cell
        The cell.
    """
    return Cell(
        State(raw["state"]),
        tuple(Finding(**f) for f in raw["findings"]),
        tuple(Exemption(**e) for e in raw["exemptions"]),
        tuple(Finding(**f) for f in raw["unproven"]),
    )


def _repo_from_json(raw: Json) -> RepoResult:
    """Rebuild one repository row.

    Returns
    -------
    RepoResult
        The row.
    """
    return RepoResult(
        raw["name"],
        raw["sha"],
        frozenset(Trait(t) for t in raw["traits"]),
        {rule_id: _cell_from_json(cell) for rule_id, cell in raw["cells"].items()},
    )


def _rule_from_json(raw: Json) -> RuleInfo:
    """Rebuild one rule column.

    Returns
    -------
    RuleInfo
        The column.
    """
    applies_to = Trait(raw["applies_to"]) if raw["applies_to"] else None
    return RuleInfo(raw["id"], raw["name"], raw["version"], raw["block"], applies_to)


def _cell_to_json(cell: Cell) -> Json:
    """Flatten one cell.

    Returns
    -------
    Json
        The cell as plain data.
    """
    return {
        "state": cell.state.value,
        "findings": [vars_of(f) for f in cell.findings],
        "exemptions": [vars_of(e) for e in cell.exemptions],
        "unproven": [vars_of(f) for f in cell.unproven],
    }


def vars_of(item: Finding | Exemption) -> Json:
    """Return a slotted dataclass's fields as a dict.

    Parameters
    ----------
    item
        A finding or an exemption.

    Returns
    -------
    Json
        Field name to value.
    """
    return {name: getattr(item, name) for name in item.__slots__}


def dumps(sweep: Sweep) -> str:
    """Serialise a sweep.

    Parameters
    ----------
    sweep
        The sweep to write.

    Returns
    -------
    str
        Indented JSON; round-trips through `loads`.
    """
    repos = [
        {
            "name": r.name,
            "sha": r.sha,
            "traits": sorted(t.value for t in r.traits),
            "cells": {rule_id: _cell_to_json(c) for rule_id, c in r.cells.items()},
        }
        for r in sweep.repos
    ]
    rules = [
        {
            "id": r.id,
            "name": r.name,
            "version": r.version,
            "block": r.block,
            "applies_to": r.applies_to.value if r.applies_to else None,
        }
        for r in sweep.rules
    ]
    document = {
        "owner": sweep.owner,
        "generated_at": sweep.generated_at,
        "concordat_version": sweep.concordat_version,
        "concordat_commit": sweep.concordat_commit,
        "excluded": vars_excluded(sweep.excluded),
        "rules": rules,
        "repos": repos,
    }
    return json.dumps(document, indent=1)


def vars_excluded(excluded: Excluded) -> Json:
    """Return the exclusion counts as a dict.

    Returns
    -------
    Json
        Forks, archived and private counts.
    """
    return {
        "forks": excluded.forks,
        "archived": excluded.archived,
        "private": excluded.private,
    }


def loads(text: str) -> Sweep:
    """Parse a sweep written by `dumps`.

    Parameters
    ----------
    text
        The JSON document.

    Returns
    -------
    Sweep
        The sweep.

    Examples
    --------
    >>> from .model import Excluded
    >>> empty = Sweep("o", "t", "1", "c", (), (), Excluded(0, 0, None))
    >>> loads(dumps(empty)) == empty
    True
    """
    raw = json.loads(text)
    return Sweep(
        owner=raw["owner"],
        generated_at=raw["generated_at"],
        concordat_version=raw["concordat_version"],
        concordat_commit=raw["concordat_commit"],
        rules=tuple(_rule_from_json(r) for r in raw["rules"]),
        repos=tuple(_repo_from_json(r) for r in raw["repos"]),
        excluded=Excluded(**raw["excluded"]),
    )
