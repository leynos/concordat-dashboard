"""The sweep file round-trips, so `render` can run apart from `sweep`."""

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
