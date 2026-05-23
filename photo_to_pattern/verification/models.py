"""Verification report models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

VerificationSeverity = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class VerificationIssue:
    severity: VerificationSeverity
    primitive_id: str
    round_number: int | None
    message: str


@dataclass(frozen=True)
class VerificationReport:
    issues: tuple[VerificationIssue, ...]

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

