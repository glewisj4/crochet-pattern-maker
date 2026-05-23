"""Export generated rounds to a strict intermediate grammar."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from photo_to_pattern.geometric_math import PatternMap, RoundSpec


def export_strict_pattern(pattern_map: PatternMap, output_path: str | Path, title: str) -> Path:
    """Write a machine-checkable pattern grammar for future 3D simulators."""

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(to_strict_pattern(pattern_map, title), encoding="utf-8")
    return destination


def to_strict_pattern(pattern_map: PatternMap, title: str) -> str:
    grouped: dict[str, list[RoundSpec]] = defaultdict(list)
    for round_spec in pattern_map.rounds:
        grouped[round_spec.primitive_id].append(round_spec)

    lines = [
        'FORMAT "PhotoToPatternStrict" 1',
        f'TITLE "{_escape(title)}"',
        "TERMINOLOGY US",
        "STYLE SPIRAL_ROUNDS",
    ]
    for primitive_id in sorted(grouped):
        lines.append(f'PART "{_escape(primitive_id)}"')
        previous = 0
        for round_spec in sorted(grouped[primitive_id], key=lambda item: item.round_number):
            lines.append(_round_line(round_spec, previous))
            previous = round_spec.stitch_count
        lines.append("END_PART")
    lines.append("END_PATTERN")
    return "\n".join(lines) + "\n"


def _round_line(round_spec: RoundSpec, expected_previous: int) -> str:
    placements = ",".join(str(item) for item in round_spec.placements) if round_spec.placements else "-"
    return (
        f"ROUND {round_spec.round_number} "
        f"FROM {expected_previous} "
        f"TO {round_spec.stitch_count} "
        f"ACTION {round_spec.action.upper()} "
        f"DELTA {round_spec.delta} "
        f"PLACEMENTS {placements}"
    )


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')

