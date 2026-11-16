"""Failure reasons reach a public page, so credentials must never survive."""

import pytest

from concordat_dashboard.redact import MAX_REASON, REDACTED, public_reason


@pytest.mark.parametrize(
    "secret",
    [
        "ghp_" + "a" * 36,
        "github_pat_" + "B" * 30,
        "gho_" + "c" * 20,
    ],
)
def test_github_tokens_are_redacted(secret: str) -> None:
    """Every GitHub token family is replaced wherever it appears."""
    reason = public_reason(f"fetch failed: token {secret} was rejected, {secret}")
    assert secret not in reason, "a token survived"
    assert REDACTED in reason, "the redaction is visible"


def test_url_credentials_are_redacted() -> None:
    """A credential embedded in a clone URL is removed."""
    reason = public_reason("fatal: https://x-access-token:s3cr3t@github.com/o/r.git")
    assert "s3cr3t" not in reason, "the URL credential survived"
    assert "github.com/o/r.git" in reason, "the rest of the message is kept"


def test_bearer_header_values_are_redacted() -> None:
    """An Authorization header echoed into an error is removed."""
    reason = public_reason("sent Authorization: Bearer abcdefghijklmnop0123456789")
    assert "abcdefghijklmnop0123456789" not in reason, "the bearer value survived"


def test_reasons_are_one_line_and_bounded() -> None:
    """A multi-line stderr becomes one bounded line."""
    reason = public_reason("line one\n" + "x" * 1000)
    assert "\n" not in reason, "the reason must be one line"
    assert len(reason) == MAX_REASON, "the reason must be truncated"


def test_plain_messages_pass_through() -> None:
    """Nothing is lost from an ordinary message."""
    assert public_reason("the rule could not run: no such file") == (
        "the rule could not run: no such file"
    ), "an ordinary message must be unchanged"
