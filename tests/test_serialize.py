"""The sweep file round-trips, so `render` can run apart from `sweep`."""

import dataclasses
import json
import typing as typ

from concordat_dashboard.serialize import dumps, loads

if typ.TYPE_CHECKING:
    from concordat_dashboard.model import Sweep


def test_sweep_round_trips(sweep: Sweep) -> None:
    """Everything written can be read back identically."""
    assert loads(dumps(sweep)) == sweep, "the sweep must survive a round trip"


def test_sweep_file_is_plain_json_with_states_as_words(sweep: Sweep) -> None:
    """The file is readable by other tools."""
    document = json.loads(dumps(sweep))
    states = {
        cell["state"] for repo in document["repos"] for cell in repo["cells"].values()
    }
    expected = {
        "compliant",
        "noncompliant",
        "indeterminate",
        "exempt",
        "not_applicable",
    }
    assert states == expected, "every state is written as a word"


def test_unknown_private_count_round_trips_as_null(sweep: Sweep) -> None:
    """None survives, so the page can omit the line."""
    document = json.loads(dumps(sweep))
    document["excluded"]["private"] = None
    restored = loads(json.dumps(document))
    assert restored.excluded.private is None, "an unknown count must stay None"


def test_unauthenticated_flag_is_written_and_read_back(sweep: Sweep) -> None:
    """sweep.json records a run that had no token; older files read as authenticated."""
    flagged = dataclasses.replace(sweep, authenticated=False)
    document = json.loads(dumps(flagged))
    assert document["authenticated"] is False, "the flag is in sweep.json"
    assert loads(dumps(flagged)).authenticated is False, "and survives the round trip"
    del document["authenticated"]
    assert loads(json.dumps(document)).authenticated is True, "absent means true"
