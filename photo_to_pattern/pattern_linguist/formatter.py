"""Format stitch maps into standard US amigurumi notation."""

from collections import defaultdict

from photo_to_pattern.geometric_math import PatternMap, RoundSpec

from .grammar import validate_round_line
from .models import CrochetPattern, PatternSection


class PatternFormatter:
    def format(self, pattern_map: PatternMap, title: str = "Photo-to-Amigurumi Pattern") -> CrochetPattern:
        grouped: dict[str, list[RoundSpec]] = defaultdict(list)
        for round_spec in pattern_map.rounds:
            grouped[round_spec.primitive_id].append(round_spec)

        sections: list[PatternSection] = []
        warnings = list(pattern_map.warnings)

        for primitive_id, rounds in grouped.items():
            lines = tuple(_format_round(round_spec) for round_spec in rounds)
            invalid = [line for line in lines if not validate_round_line(line)]
            if invalid:
                warnings.append(f"{primitive_id}: formatter emitted invalid notation.")
            notes = tuple(sorted({round_spec.note for round_spec in rounds if round_spec.note}))
            sections.append(
                PatternSection(
                    primitive_id=primitive_id,
                    title=f"{primitive_id.replace('_', ' ').title()}",
                    lines=lines,
                    notes=notes,
                )
            )

        return CrochetPattern(
            title=title,
            stitch_style="Spiral rounds",
            terminology="US crochet",
            sections=tuple(sections),
            warnings=tuple(warnings),
        )


def _format_round(round_spec: RoundSpec) -> str:
    prefix = f"R{round_spec.round_number}:"
    count = f"({round_spec.stitch_count} sts)"

    if round_spec.action == "mr":
        return f"{prefix} MR, {round_spec.stitch_count} Sc {count}"
    if round_spec.action == "even":
        return f"{prefix} Sc around {count}"
    if round_spec.action == "inc":
        body = _format_operation_round(round_spec.previous_stitch_count, round_spec.delta, "Inc")
        return f"{prefix} {body} {count}"
    body = _format_operation_round(round_spec.previous_stitch_count, abs(round_spec.delta), "Inv Dec")
    return f"{prefix} {body} {count}"


def _format_operation_round(previous_count: int, operations: int, op_token: str) -> str:
    if operations <= 0:
        return "Sc around"
    if previous_count <= operations:
        return f"{op_token} around"

    if previous_count % operations == 0:
        sc_between = max(0, previous_count // operations - (2 if op_token == "Inv Dec" else 1))
        if sc_between <= 0:
            return f"({op_token}) x {operations}"
        return f"({sc_between} Sc, {op_token}) x {operations}"

    base = max(1, previous_count // operations)
    return f"Stagger {operations} {op_token} evenly, about every {base} stitches"

