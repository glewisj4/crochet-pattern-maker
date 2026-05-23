"""Small validation grammar for generated crochet instructions."""

from __future__ import annotations

import re

ROUND_RE = re.compile(r"^R\d+: .+ \(\d+ sts\)$")
TOKEN_RE = re.compile(r"MR|Sc|Inc|Inv Dec|around|\(|\)|x \d+|\d+")


def validate_round_line(line: str) -> bool:
    """Accept the controlled notation emitted by the formatter."""

    if not ROUND_RE.match(line):
        return False
    body = line.split(": ", 1)[1].rsplit(" (", 1)[0]
    tokens = TOKEN_RE.findall(body)
    return bool(tokens)

