"""Planned-part crochet round generation."""

from __future__ import annotations

from math import ceil

from photo_to_pattern.geometric_math import GeometricConfig, PatternMap, RoundSpec
from photo_to_pattern.geometric_math.staggering import stagger_positions
from photo_to_pattern.planning.models import DesignPart, PlanningModel


class PlannedPartPatternGenerator:
    """Generate round maps for every crocheted planned part."""

    def __init__(self, config: GeometricConfig | None = None) -> None:
        self.config = config or GeometricConfig()

    def generate(self, model: PlanningModel) -> PatternMap:
        rounds: list[RoundSpec] = []
        warnings: list[str] = []
        for part in model.parts:
            if _is_surface_detail(part):
                continue
            quantity = _quantity_for_part(part, model)
            for index in range(1, quantity + 1):
                part_id = _part_id(part, index if quantity > 1 else None)
                profile = _profile_for_part(part, model, self.config)
                rounds.extend(_rounds_from_profile(part_id, profile, self.config, _note_for_part(part)))
            if part.confidence < 0.35:
                warnings.append(f"{part.name}: inferred planned part; confirm shape and attachment before crocheting.")
        return PatternMap(rounds=tuple(rounds), warnings=tuple(warnings))


def generate_planned_part_pattern_map(
    model: PlanningModel,
    config: GeometricConfig | None = None,
) -> PatternMap:
    return PlannedPartPatternGenerator(config).generate(model)


def _profile_for_part(part: DesignPart, model: PlanningModel, config: GeometricConfig) -> tuple[int, ...]:
    primitive = part.primitive.lower()
    height_inches = _part_height_inches(part, model)
    rounds = max(config.min_rounds_per_primitive, min(config.max_rounds_per_primitive, ceil(height_inches * model.options.stitches_per_inch / config.stitch_aspect_height)))
    peak = _peak_stitches(part, model, config)
    if "cone" in primitive:
        return _cone_profile(rounds, peak, config)
    if "cylinder" in primitive or "capsule" in primitive:
        return _capsule_profile(rounds, peak, config) if "capsule" in primitive else _cylinder_profile(rounds, peak, config)
    return _ovoid_profile(rounds, peak, config)


def _rounds_from_profile(
    primitive_id: str,
    profile: tuple[int, ...],
    config: GeometricConfig,
    note: str,
) -> tuple[RoundSpec, ...]:
    specs: list[RoundSpec] = []
    previous = 0
    current = config.min_stitches
    for index, target in enumerate(profile, start=1):
        if index == 1:
            current = config.min_stitches
            delta = current
            action = "mr"
            placements: tuple[int, ...] = ()
        else:
            previous = current
            current = _move_toward(current, target, config)
            delta = current - previous
            action = "inc" if delta > 0 else "dec" if delta < 0 else "even"
            placements = stagger_positions(previous, abs(delta), index)
        specs.append(
            RoundSpec(
                primitive_id=primitive_id,
                round_number=index,
                stitch_count=current,
                previous_stitch_count=previous,
                delta=delta,
                action=action,
                phase=_phase(index, len(profile), delta),
                placements=placements,
                radius=target,
                note=note,
            )
        )
    return tuple(specs)


def _move_toward(current: int, target: int, config: GeometricConfig) -> int:
    requested = target - current
    if requested > 0:
        return min(config.max_stitches_per_round, current + min(config.max_delta_per_round, requested))
    if requested < 0:
        return max(config.min_stitches, current - min(config.max_delta_per_round, abs(requested), max(1, current // 2)))
    return current


def _ovoid_profile(rounds: int, peak: int, config: GeometricConfig) -> tuple[int, ...]:
    increase_rounds = max(2, round(rounds * 0.32))
    even_rounds = max(1, round(rounds * 0.22))
    decrease_rounds = max(2, rounds - increase_rounds - even_rounds)
    counts = _ramp(config.min_stitches, peak, increase_rounds)
    counts.extend([peak] * even_rounds)
    counts.extend(_ramp(peak, config.min_stitches, decrease_rounds + 1)[1:])
    return tuple(counts[:rounds])


def _cylinder_profile(rounds: int, peak: int, config: GeometricConfig) -> tuple[int, ...]:
    cap_rounds = max(2, min(ceil((peak - config.min_stitches) / config.max_delta_per_round) + 1, rounds // 2))
    counts = _ramp(config.min_stitches, peak, cap_rounds)
    counts.extend([peak] * max(0, rounds - len(counts)))
    return tuple(counts[:rounds])


def _capsule_profile(rounds: int, peak: int, config: GeometricConfig) -> tuple[int, ...]:
    cap = max(2, rounds // 4)
    middle = max(1, rounds - cap * 2)
    counts = _ramp(config.min_stitches, peak, cap)
    counts.extend([peak] * middle)
    counts.extend(_ramp(peak, config.min_stitches, cap + 1)[1:])
    return tuple(counts[:rounds])


def _cone_profile(rounds: int, peak: int, config: GeometricConfig) -> tuple[int, ...]:
    counts = []
    current = config.min_stitches
    for index in range(rounds):
        if index == 0:
            counts.append(config.min_stitches)
            continue
        if index % 2 == 1 and current < peak:
            current = min(peak, current + min(3, config.max_delta_per_round))
        counts.append(current)
    return tuple(counts)


def _ramp(start: int, end: int, steps: int) -> list[int]:
    if steps <= 1:
        return [end]
    return [round(start + (end - start) * index / (steps - 1)) for index in range(steps)]


def _part_height_inches(part: DesignPart, model: PlanningModel) -> float:
    total = model.options.target_height_inches
    rel_height = max(0.08, part.relative_size[1])
    if part.name == "Head":
        return total * min(0.42, rel_height)
    if part.name == "Body":
        return total * min(0.55, rel_height)
    if part.name in {"Arms", "Legs"}:
        return total * min(0.38, rel_height)
    if part.name in {"Ears", "Tail"}:
        return total * min(0.30, rel_height)
    return total * rel_height


def _peak_stitches(part: DesignPart, model: PlanningModel, config: GeometricConfig) -> int:
    width_inches = max(0.25, model.options.target_height_inches * max(part.relative_size[0], part.relative_size[2]) * 0.32)
    circumference_stitches = round(width_inches * model.options.stitches_per_inch * 3.14)
    return max(config.min_stitches, min(config.max_stitches_per_round, _nearest_multiple(circumference_stitches, config.max_delta_per_round)))


def _nearest_multiple(value: int, multiple: int) -> int:
    if multiple <= 1:
        return value
    return max(multiple, round(value / multiple) * multiple)


def _part_id(part: DesignPart, index: int | None) -> str:
    base = "".join(char.lower() if char.isalnum() else "_" for char in part.name).strip("_")
    return f"{base}_{index}" if index is not None else base


def _note_for_part(part: DesignPart) -> str:
    return f"Attachment: {part.attachment}. Source: {part.source}."


def _phase(index: int, total: int, delta: int) -> str:
    if index == 1:
        return "start"
    if index == total:
        return "finish"
    if delta > 0:
        return "increase"
    if delta < 0:
        return "decrease"
    return "even"


def _is_surface_detail(part: DesignPart) -> bool:
    primitive = part.primitive.lower()
    return "detail" in primitive or "applique" in primitive or "embroidery" in primitive


def _quantity_for_part(part: DesignPart, model: PlanningModel) -> int:
    construction = next((item for item in model.construction if item.name == part.name), None)
    if construction is not None:
        return max(1, construction.quantity)
    return 2 if part.name in {"Arms", "Legs", "Ears"} else 1
