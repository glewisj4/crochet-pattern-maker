"""Generate stitch maps from voxel primitives."""

from photo_to_pattern.vision_voxelizer import Primitive3D, VoxelModel

from .models import GeometricConfig, PatternMap, RoundSpec
from .profiles import desired_profile
from .staggering import stagger_positions


class GeometricPatternGenerator:
    def __init__(self, config: GeometricConfig | None = None) -> None:
        self.config = config or GeometricConfig()

    def generate(self, model: VoxelModel) -> PatternMap:
        rounds: list[RoundSpec] = []
        warnings: list[str] = []

        for primitive in model.primitives:
            if primitive.confidence < 0.4:
                warnings.append(f"{primitive.id}: low primitive confidence; pattern needs manual review.")
            primitive_rounds = self._generate_primitive(primitive)
            rounds.extend(primitive_rounds)

        for occlusion in model.occlusions:
            warnings.append(f"Occlusion review: {occlusion.note}")

        return PatternMap(rounds=tuple(rounds), warnings=tuple(warnings))

    def _generate_primitive(self, primitive: Primitive3D) -> tuple[RoundSpec, ...]:
        desired = desired_profile(primitive, self.config)
        if not desired:
            return ()

        specs: list[RoundSpec] = []
        previous = 0
        current = self.config.min_stitches

        for index, target in enumerate(desired, start=1):
            if index == 1:
                current = self.config.min_stitches
                delta = current
                action = "mr"
                phase = "start"
                placements: tuple[int, ...] = ()
            else:
                bounded_delta = self._bounded_delta(current, target)
                previous = current
                current = max(self.config.min_stitches, current + bounded_delta)
                delta = current - previous
                action = "inc" if delta > 0 else "dec" if delta < 0 else "even"
                phase = _phase_for(index, len(desired), delta)
                placements = stagger_positions(previous, abs(delta), index)

            specs.append(
                RoundSpec(
                    primitive_id=primitive.id,
                    round_number=index,
                    stitch_count=current,
                    previous_stitch_count=previous,
                    delta=delta,
                    action=action,
                    phase=phase,
                    placements=placements,
                    radius=target,
                    note=_primitive_note(primitive),
                )
            )

        while current > self.config.min_stitches:
            index = len(specs) + 1
            bounded_delta = self._bounded_delta(current, self.config.min_stitches)
            previous = current
            current = max(self.config.min_stitches, current + bounded_delta)
            delta = current - previous
            specs.append(
                RoundSpec(
                    primitive_id=primitive.id,
                    round_number=index,
                    stitch_count=current,
                    previous_stitch_count=previous,
                    delta=delta,
                    action="dec" if delta < 0 else "even",
                    phase="finish" if current == self.config.min_stitches else "decrease",
                    placements=stagger_positions(previous, abs(delta), index),
                    radius=current,
                    note=_primitive_note(primitive),
                )
            )

        return tuple(specs)

    def _bounded_delta(self, current: int, target: int) -> int:
        requested = target - current
        if requested >= 0:
            return min(self.config.max_delta_per_round, requested)

        max_decreases_by_stability = self.config.max_delta_per_round
        max_decreases_by_consumption = max(1, current // 2)
        max_decreases = min(max_decreases_by_stability, max_decreases_by_consumption)
        return -min(abs(requested), max_decreases)


def _phase_for(index: int, total: int, delta: int) -> str:
    if index == total:
        return "finish"
    if delta > 0:
        return "increase"
    if delta < 0:
        return "decrease"
    return "even"


def _primitive_note(primitive: Primitive3D) -> str:
    if primitive.metadata.get("requires_manual_depth_order"):
        return "Confirm limb depth order before final assembly."
    if primitive.joint_hint != "none":
        return f"Preserve structural tension at {primitive.joint_hint}."
    return ""
