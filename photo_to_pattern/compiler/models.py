"""Compiler-level intermediate representation for strict crochet grammar."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


StrictSeverity = Literal["warning", "error"]
CompiledAction = Literal["MR", "INC", "DEC", "EVEN"]


@dataclass(frozen=True)
class AlignmentOffset:
    primitive_id: str
    round_number: int
    stitch_count: int
    offset_stitches: int
    drift_degrees: float


@dataclass(frozen=True)
class CompiledRound:
    primitive_id: str
    round_number: int
    from_count: int
    to_count: int
    action: CompiledAction
    delta: int
    placements: tuple[int, ...] = ()
    alignment_offset: AlignmentOffset | None = None

    @property
    def balanced(self) -> bool:
        return self.to_count == self.from_count + self.delta


@dataclass(frozen=True)
class StrictGrammarIssue:
    severity: StrictSeverity
    line_number: int
    message: str


@dataclass(frozen=True)
class StrictGrammarReport:
    rounds: tuple[CompiledRound, ...]
    issues: tuple[StrictGrammarIssue, ...]

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)
