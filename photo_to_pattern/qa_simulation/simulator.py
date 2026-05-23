"""Heuristic QA over generated round maps."""

from collections import defaultdict

from photo_to_pattern.geometric_math import GeometricConfig, PatternMap, RoundSpec
from photo_to_pattern.vision_voxelizer import VoxelModel

from .models import QAIssue, QAReport


class PatternQASimulator:
    def __init__(self, config: GeometricConfig | None = None) -> None:
        self.config = config or GeometricConfig()

    def evaluate(self, pattern_map: PatternMap, voxel_model: VoxelModel | None = None) -> QAReport:
        issues: list[QAIssue] = []
        grouped: dict[str, list[RoundSpec]] = defaultdict(list)

        for round_spec in pattern_map.rounds:
            grouped[round_spec.primitive_id].append(round_spec)
            issues.extend(self._check_round(round_spec))

        for primitive_id, rounds in grouped.items():
            issues.extend(self._check_profile(primitive_id, rounds))

        if voxel_model is not None:
            for occlusion in voxel_model.occlusions:
                issues.append(
                    QAIssue(
                        severity="warning",
                        primitive_id="model",
                        round_number=None,
                        message=f"Manual overlap review required: {occlusion.note}",
                    )
                )

        return QAReport(issues=tuple(issues))

    def _check_round(self, round_spec: RoundSpec) -> list[QAIssue]:
        issues: list[QAIssue] = []
        if abs(round_spec.delta) > self.config.max_delta_per_round:
            issues.append(
                QAIssue(
                    severity="error",
                    primitive_id=round_spec.primitive_id,
                    round_number=round_spec.round_number,
                    message="Round changes too many stitches for stable amigurumi shaping.",
                )
            )
        if round_spec.action in {"inc", "dec"} and not round_spec.placements:
            issues.append(
                QAIssue(
                    severity="error",
                    primitive_id=round_spec.primitive_id,
                    round_number=round_spec.round_number,
                    message="Increase/decrease round has no staggered placements.",
                )
            )
        return issues

    def _check_profile(self, primitive_id: str, rounds: list[RoundSpec]) -> list[QAIssue]:
        if not rounds:
            return []

        issues: list[QAIssue] = []
        max_count = max(round_spec.stitch_count for round_spec in rounds)
        even_rounds = sum(1 for round_spec in rounds if round_spec.action == "even")
        height_units = len(rounds) * self.config.stitch_aspect_height
        width_units = max_count / 6

        if width_units > 0 and height_units / width_units < 0.45:
            issues.append(
                QAIssue(
                    severity="warning",
                    primitive_id=primitive_id,
                    round_number=None,
                    message="Profile may crochet squashed; consider more even rounds or smaller hook gauge.",
                )
            )

        if max_count >= 24 and even_rounds == 0:
            issues.append(
                QAIssue(
                    severity="info",
                    primitive_id=primitive_id,
                    round_number=None,
                    message="No maintenance rounds; shape will be a sharp ovoid rather than a fuller sphere.",
                )
            )

        return issues

