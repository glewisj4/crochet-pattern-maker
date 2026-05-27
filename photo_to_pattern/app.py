"""Application orchestrator for photo-to-amigurumi pattern generation."""

from dataclasses import dataclass
from pathlib import Path

from .geometric_math import GeometricConfig, GeometricPatternGenerator, PatternMap
from .part_generator import generate_planned_part_pattern_map
from .pattern_linguist import CrochetPattern, PatternFormatter
from .pattern_linguist.models import PatternSection
from .qa_simulation import PatternQASimulator, QAReport
from .image_regions import CharacterAnalysis, CharacterRegionAnalyzer, ColorRegion
from .image_regions.shape_fit import segment_axis
from .integration import (
    RefinementReport,
    RuntimeDashboardSnapshot,
    build_runtime_dashboard_snapshot,
    refine_pattern_until_accuracy,
    target_mesh_from_pattern,
    target_mesh_from_voxel_model,
)
from .vision_voxelizer import ImageFrame, LimbOcclusion, Primitive3D, Vec2, Vec3, VisionVoxelizer, VoxelModel
from .planning.models import PlanningModel


@dataclass(frozen=True)
class AppResult:
    voxel_model: VoxelModel
    pattern_map: PatternMap
    crochet_pattern: CrochetPattern
    qa_report: QAReport
    character_analysis: CharacterAnalysis | None = None
    refinement_report: RefinementReport | None = None
    dashboard_snapshot: RuntimeDashboardSnapshot | None = None

    def render(self) -> str:
        return "\n\n".join(
            [
                self.crochet_pattern.render(),
                self.qa_report.render(),
            ]
        )


class PhotoToPatternApp:
    """Coordinates all development-plan sub-systems."""

    def __init__(self, geometric_config: GeometricConfig | None = None) -> None:
        self.vision = VisionVoxelizer()
        self.geometry = GeometricPatternGenerator(geometric_config)
        self.formatter = PatternFormatter()
        self.qa = PatternQASimulator(geometric_config)
        self.regions = CharacterRegionAnalyzer()

    def from_frame(self, frame: ImageFrame, title: str = "Photo-to-Amigurumi Pattern") -> AppResult:
        voxel_model = self.vision.process_frame(frame)
        return self._complete(voxel_model, title)

    def from_image(self, image_path: str | Path, title: str = "Photo-to-Amigurumi Pattern") -> AppResult:
        analysis = self.regions.analyze(image_path)
        voxel_model = _voxel_model_from_analysis(analysis)
        if not voxel_model.primitives:
            voxel_model = self.vision.process(image_path)
        return self._complete(voxel_model, title, analysis)

    def from_image_with_plan(
        self,
        image_path: str | Path,
        planning_model: PlanningModel,
        title: str = "Photo-to-Amigurumi Pattern",
        virtual_build_path: str | Path | None = None,
    ) -> AppResult:
        analysis = self.regions.analyze(image_path)
        voxel_model = _voxel_model_from_analysis(analysis)
        if not voxel_model.primitives:
            voxel_model = self.vision.process(image_path)
        target_mesh = target_mesh_from_voxel_model(voxel_model)
        pattern_map = self._refine_pattern_map(generate_planned_part_pattern_map(planning_model, self.geometry.config), target_mesh)
        crochet_pattern = self.formatter.format(pattern_map, title=title, planning_model=planning_model)
        crochet_pattern = _with_planned_part_sections(crochet_pattern, planning_model)
        crochet_pattern = _with_surface_detail_section(crochet_pattern, analysis)
        qa_report = self.qa.evaluate(pattern_map, voxel_model, planning_model)
        refinement_report, dashboard_snapshot = self._runtime_reports(pattern_map, target_mesh, virtual_build_path=virtual_build_path)
        return AppResult(
            voxel_model=voxel_model,
            pattern_map=pattern_map,
            crochet_pattern=crochet_pattern,
            qa_report=qa_report,
            character_analysis=analysis,
            refinement_report=refinement_report,
            dashboard_snapshot=dashboard_snapshot,
        )

    def _complete(
        self,
        voxel_model: VoxelModel,
        title: str,
        character_analysis: CharacterAnalysis | None = None,
    ) -> AppResult:
        target_mesh = target_mesh_from_voxel_model(voxel_model)
        pattern_map = self._refine_pattern_map(self.geometry.generate(voxel_model), target_mesh)
        crochet_pattern = self.formatter.format(pattern_map, title=title)
        if character_analysis is not None:
            crochet_pattern = _with_surface_detail_section(crochet_pattern, character_analysis)
        qa_report = self.qa.evaluate(pattern_map, voxel_model)
        refinement_report, dashboard_snapshot = self._runtime_reports(pattern_map, target_mesh)
        return AppResult(
            voxel_model=voxel_model,
            pattern_map=pattern_map,
            crochet_pattern=crochet_pattern,
            qa_report=qa_report,
            character_analysis=character_analysis,
            refinement_report=refinement_report,
            dashboard_snapshot=dashboard_snapshot,
        )

    def _refine_pattern_map(self, pattern_map: PatternMap, target_mesh=None) -> PatternMap:
        target_mesh = target_mesh or target_mesh_from_pattern(pattern_map)
        return refine_pattern_until_accuracy(pattern_map, target_mesh, accuracy_target=0.90).pattern_map

    def _runtime_reports(
        self,
        pattern_map: PatternMap,
        target_mesh=None,
        virtual_build_path: str | Path | None = None,
    ) -> tuple[RefinementReport, RuntimeDashboardSnapshot]:
        target_mesh = target_mesh or target_mesh_from_pattern(pattern_map)
        refinement_report = refine_pattern_until_accuracy(pattern_map, target_mesh, accuracy_target=0.90)
        dashboard_snapshot = build_runtime_dashboard_snapshot(pattern_map, refinement_report.simulation_report, virtual_build_path=virtual_build_path)
        return refinement_report, dashboard_snapshot


def _with_surface_detail_section(
    crochet_pattern: CrochetPattern,
    analysis: CharacterAnalysis,
) -> CrochetPattern:
    lines = [
        f"Image foreground bbox: {analysis.foreground_bbox[2]}w x {analysis.foreground_bbox[3]}h px at {analysis.foreground_bbox[0]}, {analysis.foreground_bbox[1]}.",
    ]

    for region in _rank_surface_regions(analysis.regions):
        lines.append(_surface_instruction(region))

    notes = tuple(analysis.warnings) if analysis.warnings else (
        "Surface details are placement guides; confirm exact embroidery/applique placement after stuffing.",
    )
    section = PatternSection(
        primitive_id="surface_details",
        title="Surface Details",
        lines=tuple(lines),
        notes=notes,
    )
    return CrochetPattern(
        title=crochet_pattern.title,
        stitch_style=crochet_pattern.stitch_style,
        terminology=crochet_pattern.terminology,
        sections=crochet_pattern.sections + (section,),
        warnings=crochet_pattern.warnings,
    )


def _with_planned_part_sections(
    crochet_pattern: CrochetPattern,
    planning_model: PlanningModel,
) -> CrochetPattern:
    materials = [
        f"Target finished height: {planning_model.options.target_height_inches:.1f} in.",
        f"Gauge target: {planning_model.options.stitches_per_inch:.1f} sts/in.",
    ]
    for part in planning_model.parts:
        quantity = _quantity_for_planned_part(part.name, planning_model)
        materials.append(
            f"{part.name} x{quantity}: {part.primitive}, attach at {part.attachment}, confidence {part.confidence:.2f}."
        )
    if planning_model.compromises:
        materials.append("")
        materials.append("Form compromises:")
        for compromise in planning_model.compromises:
            materials.append(f"{compromise.feature}: {compromise.crochet_treatment} ({compromise.reason})")

    section = PatternSection(
        primitive_id="planned_design_overview",
        title="Planned Design Overview",
        lines=tuple(materials),
        notes=("All structural planned parts now have generated crochet rounds unless listed as a surface detail.",),
    )
    return CrochetPattern(
        title=crochet_pattern.title,
        stitch_style=crochet_pattern.stitch_style,
        terminology=crochet_pattern.terminology,
        sections=(section,) + crochet_pattern.sections,
        warnings=crochet_pattern.warnings,
    )


def _quantity_for_planned_part(part_name: str, planning_model: PlanningModel) -> int:
    construction = next((item for item in planning_model.construction if item.name == part_name), None)
    if construction is not None:
        return max(1, construction.quantity)
    return 2 if part_name in {"Arms", "Legs", "Ears"} else 1


def _voxel_model_from_analysis(analysis: CharacterAnalysis) -> VoxelModel:
    body_regions = sorted(analysis.regions_of_kind("body"), key=lambda region: region.area, reverse=True)
    if not body_regions:
        return VoxelModel(primitives=())

    body = body_regions[0]
    x, y, width, height = body.bbox
    primitives: list[Primitive3D] = [
        Primitive3D(
            id="body",
            kind="ovoid",
            center=Vec3(x + width / 2, y + height / 2, 0),
            radius_x=width * 0.42,
            radius_y=height * 0.50,
            radius_z=width * 0.34,
            confidence=body.confidence,
            metadata={"source_region": "yellow_body"},
        )
    ]

    for index, leg in enumerate(sorted(analysis.regions_of_kind("leg"), key=lambda region: region.centroid[0]), start=1):
        lx, ly, leg_width, leg_height = leg.bbox
        bbox_length = max(leg_width, leg_height)
        area_thickness = leg.area / max(1, bbox_length)
        fitted_thickness = leg.median_thickness or area_thickness
        axis_length = _axis_length(leg.major_axis) if leg.major_axis else bbox_length
        axis_thickness = leg.area / max(1, axis_length)
        thickness = max(18, min(min(leg_width, leg_height), fitted_thickness * 0.45, axis_thickness * 1.35))
        max_segment_length = max(80, height * 0.16)
        axis_segments = _segments_from_centerline(leg.centerline, max_segment_length)
        if not axis_segments:
            axis_segments = segment_axis(leg.major_axis, max_segment_length) if leg.major_axis else ()
        if not axis_segments:
            axis_segments = (((lx, ly), (lx + leg_width, ly + leg_height)),)

        for segment_index, (start, end) in enumerate(axis_segments, start=1):
            center_x = (start[0] + end[0]) / 2
            center_y = (start[1] + end[1]) / 2
            length = ((start[0] - end[0]) ** 2 + (start[1] - end[1]) ** 2) ** 0.5
            primitives.append(
                Primitive3D(
                    id=f"leg_{index}_{segment_index}",
                    kind="capsule",
                    center=Vec3(center_x, center_y, 0),
                    radius_x=thickness / 2,
                    radius_y=max(thickness, length) / 2,
                    radius_z=thickness / 2 * 0.8,
                    parent_id="body" if segment_index == 1 else f"leg_{index}_{segment_index - 1}",
                    joint_hint="hip" if segment_index == 1 else "knee",
                    confidence=leg.confidence,
                    metadata={
                        "source_region": "dark_leg",
                        "requires_manual_depth_order": True,
                        "fitted_from_axis": True,
                    },
                )
            )

    occlusions = (
        LimbOcclusion(
            kind="overlap",
            location=Vec2(x + width / 2, y + height * 0.92),
            estimated_depth_order=None,
            confidence=0.68,
            note="Leg attachment and depth order inferred from flat color regions; review before final pattern.",
        ),
    )
    return VoxelModel(
        primitives=tuple(primitives),
        occlusions=occlusions,
        notes=(
            "Region-aware model generated from detected body and leg color components.",
            "Face mask and eyes are treated as surface applique/embroidery details.",
        ),
    )


def _rank_surface_regions(regions: tuple[ColorRegion, ...]) -> list[ColorRegion]:
    priority = {"body": 0, "face_mask": 1, "eye": 2, "leg": 3, "unknown": 4}
    meaningful = [
        region
        for region in regions
        if region.kind in {"body", "face_mask", "eye", "leg"}
    ]
    return sorted(meaningful, key=lambda region: (priority[region.kind], -region.area))[:8]


def _axis_length(axis: tuple[tuple[float, float], tuple[float, float]] | None) -> float:
    if axis is None:
        return 0.0
    start, end = axis
    return ((start[0] - end[0]) ** 2 + (start[1] - end[1]) ** 2) ** 0.5


def _segments_from_centerline(
    centerline: tuple[tuple[float, float], ...],
    max_segment_length: float,
) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
    if len(centerline) < 2:
        return ()
    segments = []
    start = centerline[0]
    previous = centerline[0]
    accumulated = 0.0
    for point in centerline[1:]:
        step = ((point[0] - previous[0]) ** 2 + (point[1] - previous[1]) ** 2) ** 0.5
        accumulated += step
        if accumulated >= max_segment_length:
            segments.append((start, point))
            start = point
            accumulated = 0.0
        previous = point
    if start != centerline[-1]:
        segments.append((start, centerline[-1]))
    min_length = max(24.0, max_segment_length * 0.30)
    filtered = [
        segment
        for segment in segments
        if ((segment[0][0] - segment[1][0]) ** 2 + (segment[0][1] - segment[1][1]) ** 2) ** 0.5 >= min_length
    ]
    return tuple(filtered or segments[:1])


def _surface_instruction(region: ColorRegion) -> str:
    x, y, width, height = region.bbox
    color = f"rgb{region.average_color}"
    if region.kind == "body":
        return f"Body color region: main yellow form, bbox {width}w x {height}h at {x}, {y}, average {color}."
    if region.kind == "face_mask":
        return f"Face mask: crochet or felt an oval/teardrop applique, bbox {width}w x {height}h at {x}, {y}, average {color}."
    if region.kind == "eye":
        return f"Eye: small pale oval applique or embroidery, bbox {width}w x {height}h at {x}, {y}, average {color}."
    if region.kind == "leg":
        return f"Leg/foot: dark narrow appendage candidate, bbox {width}w x {height}h at {x}, {y}, average {color}."
    return f"Unclassified color region: bbox {width}w x {height}h at {x}, {y}, average {color}."
