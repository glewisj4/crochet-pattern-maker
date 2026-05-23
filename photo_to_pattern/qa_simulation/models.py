"""QA report models."""

from dataclasses import dataclass
from typing import Literal

Severity = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class QAIssue:
    severity: Severity
    primitive_id: str
    round_number: int | None
    message: str


@dataclass(frozen=True)
class QAReport:
    issues: tuple[QAIssue, ...]

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def render(self) -> str:
        if not self.issues:
            return "QA: passed with no issues."
        lines = ["QA report:"]
        for issue in self.issues:
            scope = issue.primitive_id
            if issue.round_number is not None:
                scope += f" R{issue.round_number}"
            lines.append(f"- {issue.severity.upper()} {scope}: {issue.message}")
        return "\n".join(lines)

