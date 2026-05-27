"""Parser and arithmetic validator for the strict `.cr` grammar."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
import re

from .models import AlignmentOffset, CompiledRound, StrictGrammarIssue, StrictGrammarReport


ROUND_RE = re.compile(
    r"^ROUND (?P<round>\d+) FROM (?P<from>\d+) TO (?P<to>\d+) "
    r"ACTION (?P<action>MR|INC|DEC|EVEN) DELTA (?P<delta>-?\d+) "
    r"PLACEMENTS (?P<placements>-|\d+(?:,\d+)*)$"
)
OFFSET_RE = re.compile(
    r"^OFFSET ROUND (?P<round>\d+) STITCH_COUNT (?P<count>\d+) "
    r"SHIFT (?P<shift>\d+) DRIFT (?P<drift>-?\d+(?:\.\d+)?)$"
)
PART_RE = re.compile(r'^PART "(?P<name>(?:[^"\\]|\\.)*)"$')
TITLE_RE = re.compile(r'^TITLE "(?:[^"\\]|\\.)*"$')


def validate_strict_pattern(text: str) -> StrictGrammarReport:
    """Parse a strict pattern script and return all arithmetic issues."""

    rounds, issues = _parse(text)
    issues.extend(_validate_round_sequences(rounds))
    return StrictGrammarReport(rounds=tuple(rounds), issues=tuple(issues))


def parse_strict_pattern(text: str) -> tuple[CompiledRound, ...]:
    """Parse strict grammar and raise ValueError if any error is found."""

    report = validate_strict_pattern(text)
    if not report.passed:
        detail = "; ".join(issue.message for issue in report.issues if issue.severity == "error")
        raise ValueError(detail or "Strict pattern validation failed.")
    return report.rounds


def _parse(text: str) -> tuple[list[CompiledRound], list[StrictGrammarIssue]]:
    rounds: list[CompiledRound] = []
    issues: list[StrictGrammarIssue] = []
    current_part: str | None = None
    pending_offsets: dict[tuple[str, int], AlignmentOffset] = {}

    lines = [(line_number, line.strip()) for line_number, line in enumerate(text.splitlines(), start=1) if line.strip()]
    if not lines or lines[0][1] != 'FORMAT "PhotoToPatternStrict" 1':
        issues.append(StrictGrammarIssue("error", 1, "Missing strict grammar format header."))

    saw_end_pattern = False
    closed_parts: set[str] = set()
    header_state = 0
    required_headers = {
        'FORMAT "PhotoToPatternStrict" 1': 0,
        "TITLE": 1,
        "TERMINOLOGY US": 2,
        "STYLE SPIRAL_ROUNDS": 3,
    }
    for line_number, line in lines:
        if saw_end_pattern:
            issues.append(StrictGrammarIssue("error", line_number, "No content is allowed after END_PATTERN."))
            continue
        if line == 'FORMAT "PhotoToPatternStrict" 1':
            if current_part is not None:
                issues.append(StrictGrammarIssue("error", line_number, "FORMAT is not allowed inside PART."))
            if header_state != required_headers[line]:
                issues.append(StrictGrammarIssue("error", line_number, "FORMAT header is out of order."))
            header_state = max(header_state, 1)
            continue
        if TITLE_RE.match(line):
            if current_part is not None:
                issues.append(StrictGrammarIssue("error", line_number, "TITLE is not allowed inside PART."))
            if header_state != required_headers["TITLE"]:
                issues.append(StrictGrammarIssue("error", line_number, "TITLE header is missing or out of order."))
            header_state = max(header_state, 2)
            continue
        if line == "TERMINOLOGY US":
            if current_part is not None:
                issues.append(StrictGrammarIssue("error", line_number, "TERMINOLOGY is not allowed inside PART."))
            if header_state != required_headers[line]:
                issues.append(StrictGrammarIssue("error", line_number, "TERMINOLOGY header is missing or out of order."))
            header_state = max(header_state, 3)
            continue
        if line == "STYLE SPIRAL_ROUNDS":
            if current_part is not None:
                issues.append(StrictGrammarIssue("error", line_number, "STYLE is not allowed inside PART."))
            if header_state != required_headers[line]:
                issues.append(StrictGrammarIssue("error", line_number, "STYLE header is missing or out of order."))
            header_state = max(header_state, 4)
            continue
        part_match = PART_RE.match(line)
        if part_match:
            if header_state < 4:
                issues.append(StrictGrammarIssue("error", line_number, "PART cannot begin before required headers."))
            if current_part is not None:
                issues.append(StrictGrammarIssue("error", line_number, "Nested PART blocks are not allowed."))
            current_part = _unescape(part_match.group("name"))
            continue
        if line == "END_PART":
            if current_part is None:
                issues.append(StrictGrammarIssue("error", line_number, "END_PART without active PART."))
            else:
                closed_parts.add(current_part)
            current_part = None
            continue
        if line == "END_PATTERN":
            if current_part is not None:
                issues.append(StrictGrammarIssue("error", line_number, "PART must be closed before END_PATTERN."))
            saw_end_pattern = True
            continue
        if current_part is None:
            issues.append(StrictGrammarIssue("error", line_number, f"Unexpected line outside PART: {line}"))
            continue

        offset_match = OFFSET_RE.match(line)
        if offset_match:
            round_number = int(offset_match.group("round"))
            stitch_count = int(offset_match.group("count"))
            shift = int(offset_match.group("shift"))
            drift = float(offset_match.group("drift"))
            if stitch_count <= 0 or shift < 0 or shift >= stitch_count:
                issues.append(StrictGrammarIssue("error", line_number, "OFFSET shift must be within 0..STITCH_COUNT-1."))
            pending_offsets[(current_part, round_number)] = AlignmentOffset(current_part, round_number, stitch_count, shift, drift)
            continue

        round_match = ROUND_RE.match(line)
        if not round_match:
            issues.append(StrictGrammarIssue("error", line_number, f"Invalid strict grammar line: {line}"))
            continue

        placements = _parse_placements(round_match.group("placements"))
        compiled = CompiledRound(
            primitive_id=current_part,
            round_number=int(round_match.group("round")),
            from_count=int(round_match.group("from")),
            to_count=int(round_match.group("to")),
            action=round_match.group("action"),  # type: ignore[arg-type]
            delta=int(round_match.group("delta")),
            placements=placements,
        )
        rounds.append(compiled)
        issues.extend(_validate_round(compiled, line_number))

    if current_part is not None:
        issues.append(StrictGrammarIssue("error", lines[-1][0] if lines else 1, "PART block was not closed with END_PART."))
    part_names = {round_spec.primitive_id for round_spec in rounds}
    missing_end_parts = part_names.difference(closed_parts)
    for part_name in sorted(missing_end_parts):
        issues.append(StrictGrammarIssue("error", 0, f"{part_name}: missing END_PART."))
    if not saw_end_pattern:
        issues.append(StrictGrammarIssue("error", lines[-1][0] if lines else 1, "Missing END_PATTERN."))
    if header_state < 4:
        issues.append(StrictGrammarIssue("error", 0, "Strict grammar requires FORMAT, TITLE, TERMINOLOGY, and STYLE headers."))
    issues.extend(_validate_offsets(rounds, pending_offsets))
    return _attach_offsets(rounds, pending_offsets), issues


def _validate_round(round_spec: CompiledRound, line_number: int) -> list[StrictGrammarIssue]:
    issues: list[StrictGrammarIssue] = []
    if not round_spec.balanced:
        issues.append(StrictGrammarIssue("error", line_number, "Round arithmetic must satisfy TO == FROM + DELTA."))
    if round_spec.action == "MR" and (round_spec.from_count != 0 or round_spec.delta <= 0):
        issues.append(StrictGrammarIssue("error", line_number, "MR rounds must start from zero and add stitches."))
    if round_spec.action == "INC" and round_spec.delta <= 0:
        issues.append(StrictGrammarIssue("error", line_number, "INC rounds must have a positive delta."))
    if round_spec.action == "DEC" and round_spec.delta >= 0:
        issues.append(StrictGrammarIssue("error", line_number, "DEC rounds must have a negative delta."))
    if round_spec.action == "EVEN" and round_spec.delta != 0:
        issues.append(StrictGrammarIssue("error", line_number, "EVEN rounds must have zero delta."))

    if round_spec.action in {"INC", "DEC"}:
        expected = abs(round_spec.delta)
        if len(round_spec.placements) != expected:
            issues.append(StrictGrammarIssue("error", line_number, "Placement count must equal abs(DELTA)."))
        if len(set(round_spec.placements)) != len(round_spec.placements):
            issues.append(StrictGrammarIssue("error", line_number, "Placements must be unique."))
        if tuple(sorted(round_spec.placements)) != round_spec.placements:
            issues.append(StrictGrammarIssue("error", line_number, "Placements must be sorted."))
        invalid = [placement for placement in round_spec.placements if placement < 1 or placement > round_spec.from_count]
        if invalid:
            issues.append(StrictGrammarIssue("error", line_number, "Placements must be within 1..FROM."))
    elif round_spec.placements:
        issues.append(StrictGrammarIssue("error", line_number, "Only INC and DEC rounds may include placements."))
    return issues


def _validate_round_sequences(rounds: list[CompiledRound]) -> list[StrictGrammarIssue]:
    issues: list[StrictGrammarIssue] = []
    grouped: dict[str, list[CompiledRound]] = defaultdict(list)
    for round_spec in rounds:
        grouped[round_spec.primitive_id].append(round_spec)

    for primitive_id, primitive_rounds in grouped.items():
        previous_to = 0
        for expected_round, round_spec in enumerate(sorted(primitive_rounds, key=lambda item: item.round_number), start=1):
            if round_spec.round_number != expected_round:
                issues.append(StrictGrammarIssue("error", 0, f"{primitive_id}: round numbers must be contiguous."))
            if round_spec.from_count != previous_to:
                issues.append(StrictGrammarIssue("error", 0, f"{primitive_id}: FROM must match previous TO."))
            previous_to = round_spec.to_count
    return issues


def _validate_offsets(
    rounds: list[CompiledRound],
    offsets: dict[tuple[str, int], AlignmentOffset],
) -> list[StrictGrammarIssue]:
    issues: list[StrictGrammarIssue] = []
    round_lookup = {(round_spec.primitive_id, round_spec.round_number): round_spec for round_spec in rounds}
    for key, offset in offsets.items():
        round_spec = round_lookup.get(key)
        if round_spec is None:
            issues.append(StrictGrammarIssue("error", 0, f"{offset.primitive_id}: OFFSET references missing round {offset.round_number}."))
            continue
        if offset.stitch_count != round_spec.to_count:
            issues.append(
                StrictGrammarIssue(
                    "error",
                    0,
                    f"{offset.primitive_id}: OFFSET STITCH_COUNT must match round {offset.round_number} TO count.",
                )
            )
        if offset.offset_stitches < 0 or offset.offset_stitches >= round_spec.to_count:
            issues.append(StrictGrammarIssue("error", 0, f"{offset.primitive_id}: OFFSET SHIFT is outside the round stitch count."))
    return issues


def _attach_offsets(
    rounds: list[CompiledRound],
    offsets: dict[tuple[str, int], AlignmentOffset],
) -> list[CompiledRound]:
    attached: list[CompiledRound] = []
    for round_spec in rounds:
        attached.append(
            replace(
                round_spec,
                alignment_offset=offsets.get((round_spec.primitive_id, round_spec.round_number)),
            )
        )
    return attached


def _parse_placements(value: str) -> tuple[int, ...]:
    if value == "-":
        return ()
    return tuple(int(item) for item in value.split(","))


def _unescape(value: str) -> str:
    return value.replace('\\"', '"').replace("\\\\", "\\")
