"""Make an error message safe to publish.

A failure reason becomes finding text on a public page and in `sweep.json`.
Subprocess and API errors can carry a credential or a URL with one embedded, so
every reason passes through here before it is stored.
"""

import re

REDACTED = "[redacted]"
MAX_REASON = 240
SECRET_PATTERNS = (
    # GitHub token families: classic, fine-grained, OAuth, app and refresh.
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{16,})\b"),
    # An `Authorization: Bearer ...` or `token ...` header value.
    re.compile(r"(?i)\b(?:bearer|token)\s+[A-Za-z0-9._~+/=-]{16,}"),
    # Credentials embedded in a URL: https://user:secret@host/...
    re.compile(r"(?<=://)[^/@\s]+@"),
)


def public_reason(text: str) -> str:
    """Return *text* with credentials removed, on one line, and truncated.

    Parameters
    ----------
    text
        A raw error message.

    Returns
    -------
    str
        A single-line message of at most `MAX_REASON` characters in which every
        token-shaped string and URL credential is replaced.

    Examples
    --------
    >>> public_reason("fetch https://x-access-token:abc@github.com/o/r failed")
    'fetch https://[redacted]github.com/o/r failed'
    """
    cleaned = " ".join(text.split())
    for pattern in SECRET_PATTERNS:
        cleaned = pattern.sub(REDACTED, cleaned)
    return cleaned[:MAX_REASON]
