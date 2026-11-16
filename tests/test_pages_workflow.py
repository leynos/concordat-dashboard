"""The publishing workflow keeps its privilege boundary and pins every action."""

import pathlib
import re
import typing as typ

import pytest
import yaml

WORKFLOW = pathlib.Path(__file__).parents[1] / ".github" / "workflows" / "pages.yml"
FULL_SHA = re.compile(r"@[0-9a-f]{40}$")


@pytest.fixture(scope="module")
def workflow() -> dict[str, typ.Any]:
    """Load the Pages workflow.

    Returns
    -------
    dict[str, typ.Any]
        The parsed workflow; PyYAML reads the `on` key as `True`.
    """
    return yaml.safe_load(WORKFLOW.read_text("utf-8"))


def test_runs_on_a_schedule_and_on_demand(workflow: dict[str, typ.Any]) -> None:
    """The page refreshes daily and can be rebuilt by hand."""
    triggers = typ.cast("dict[bool, typ.Any]", workflow)[True]
    assert "schedule" in triggers, "the sweep must be scheduled"
    assert "workflow_dispatch" in triggers, "the sweep must be dispatchable"
    assert "pull_request" not in triggers, "a pull request must not deploy"


def test_default_token_is_read_only_and_only_deploy_can_write_pages(
    workflow: dict[str, typ.Any],
) -> None:
    """Only the deploy job may write Pages or mint an OIDC token."""
    jobs = workflow["jobs"]
    assert workflow["permissions"] == {"contents": "read"}, "read-only default"
    assert "permissions" not in jobs["build"], "build inherits the read-only default"
    deploy = jobs["deploy"]["permissions"]
    assert deploy == {"pages": "write", "id-token": "write"}, "deploy may publish"


def test_deploy_waits_for_a_successful_build(workflow: dict[str, typ.Any]) -> None:
    """A failed sweep leaves the previous page in place."""
    assert workflow["jobs"]["deploy"]["needs"] == "build", "deploy needs build"


def test_every_action_is_pinned_to_a_full_commit_sha(
    workflow: dict[str, typ.Any],
) -> None:
    """A moved tag must not change what the workflow runs."""
    uses = [
        step["uses"]
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if "uses" in step
    ]
    unpinned = [u for u in uses if not FULL_SHA.search(u)]
    assert uses, "the workflow uses actions"
    assert not unpinned, f"actions not pinned to a full SHA: {unpinned}"


def test_no_secret_or_self_hosted_runner_is_referenced() -> None:
    """The sweep needs only the built-in token, on GitHub-hosted runners."""
    text = WORKFLOW.read_text("utf-8")
    assert "secrets." not in text, "no repository secret may be referenced"
    assert "ubicloud" not in text, "the sweep runs on GitHub-hosted runners"
