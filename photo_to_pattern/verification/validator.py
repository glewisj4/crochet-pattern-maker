"""Strict stitch-map validation for generated crochet plans."""

from __future__ import annotations

from collections import defaultdict

from photo_to_pattern.geometric_math import GeometricConfig, PatternMap, RoundSpec

from .models import VerificationIssue, VerificationReport


def validate_pattern_map(
    pattern_map: PatternMap,
    config: GeometricConfig | None = None,
) -> VerificationReport:
    config = config or GeometricConfig()
    grouped: dict[str, list[RoundSpec]] = defaultdict(list)
    issues: list[VerificationIssue] = []

    for round_spec in pattern_map.rounds:
        grouped[round_spec.primitive_id].append(round_spec)

    for primitive_id, rounds in grouped.items():
        previous = 0
        seen_numbers: set[int] = set()
        for round_spec in sorted(rounds, key=lambda item: item.round_number):
            if round_spec.round_number in seen_numbers:
                issues.append(_issue("error", primitive_id, round_spec.round_number, "Duplicate round number."))
            seen_numbers.add(round_spec.round_number)
            issues.extend(_validate_round(round_spec, previous, config))
            previous = round_spec.stitch_count
        issues.extend(_validate_shape_profile(primitive_id, rounds))

    if not grouped:
        issues.append(_issue("error", "pattern", None, "Pattern contains no rounds."))

    return VerificationReport(tuple(issues))


def _validate_round(round_spec: RoundSpec, expected_previous: int, config: GeometricConfig) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    primitive_id = round_spec.primitive_id
    round_number = round_spec.round_number

    if round_spec.previous_stitch_count != expected_previous:
        issues.append(
            _issue(
                "error",
                primitive_id,
                round_number,
                f"Previous stitch count mismatch: expected {expected_previous}, got {round_spec.previous_stitch_count}.",
            )
        )

    actual_delta = round_spec.stitch_count - expected_previous
    if round_spec.delta != actual_delta:
        issues.append(_issue("error", primitive_id, round_number, f"Delta mismatch: expected {actual_delta}, got {round_spec.delta}."))

    if round_spec.stitch_count < config.min_stitches:
        issues.append(_issue("error", primitive_id, round_number, "Round stitch count is below minimum."))
    if round_spec.stitch_count > config.max_stitches_per_round:
        issues.append(_issue("warning", primitive_id, round_number, "Round exceeds preferred maximum stitch count."))
    if abs(round_spec.delta) > config.max_delta_per_round:
        issues.append(_issue("error", primitive_id, round_number, "Round changes too many stitches for stable shaping."))

    if round_spec.action == "mr" and expected_previous != 0:
        issues.append(_issue("error", primitive_id, round_number, "Magic-ring round must start a piece."))
    if round_spec.action == "even" and round_spec.delta != 0:
        issues.append(_issue("error", primitive_id, round_number, "Even round must not change stitch count."))
    if round_spec.action == "inc" and round_spec.delta <= 0:
        issues.append(_issue("error", primitive_id, round_number, "Increase round must increase stitch count."))
    if round_spec.action == "dec" and round_spec.delta >= 0:
        issues.append(_issue("error", primitive_id, round_number, "Decrease round must decrease stitch count."))

    if round_spec.action in {"inc", "dec"} and len(round_spec.placements) != abs(round_spec.delta):
        issues.append(_issue("error", primitive_id, round_number, "Placement count does not match stitch-count change."))

    return issues


def _validate_shape_profile(primitive_id: str, rounds: list[RoundSpec]) -> list[VerificationIssue]:
    sorted_rounds = sorted(rounds, key=lambda item: item.round_number)
    if len(sorted_rounds) < 4:
        return [_issue("warning", primitive_id, None, "Piece has very few rounds; finished shape may be underspecified.")]

    max_index = max(range(len(sorted_rounds)), key=lambda index: sorted_rounds[index].stitch_count)
    if max_index == 0 or max_index == len(sorted_rounds) - 1:
        return [_issue("warning", primitive_id, None, "Widest round is at an edge; piece may not close as intended.")]
    return []


def _issue(
    severity: str,
    primitive_id: str,
    round_number: int | None,
    message: str,
) -> VerificationIssue:
    return VerificationIssue(severity=severity, primitive_id=primitive_id, round_number=round_number, message=message)  # type: ignore[arg-type]

