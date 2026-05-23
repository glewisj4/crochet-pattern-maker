"""Export complete pattern-plan bundles."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import shutil

from .app import AppResult
from .accuracy import build_accuracy_report
from .planning import PlanningResult
from .report import export_clean_report
from .preview import render_analysis_preview
from .verification import (
    export_stitch_graph,
    export_strict_pattern,
    render_design_proof,
    render_stitch_simulation,
    validate_pattern_map,
    validate_stitch_graph,
)
from .verification.stitch_graph import to_stitch_graph


def export_plan_bundle(
    result: AppResult,
    source_image: str | Path,
    output_dir: str | Path,
    project_name: str = "photo_to_pattern_plan",
) -> Path:
    """Export pattern text, original image, preview image, and metadata."""

    source = Path(source_image)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    safe_name = _safe_name(project_name)
    original_path = destination / f"{safe_name}_original{source.suffix.lower() or '.png'}"
    preview_path = destination / f"{safe_name}_preview.jpg"
    pattern_path = destination / f"{safe_name}_pattern.txt"
    details_path = destination / f"{safe_name}_details.json"
    strict_path = destination / f"{safe_name}_pattern.strict"
    verification_path = destination / f"{safe_name}_verification.json"
    simulation_path = destination / f"{safe_name}_stitch_simulation.jpg"
    stitch_graph_path = destination / f"{safe_name}_stitch_graph.json"

    shutil.copy2(source, original_path)
    if result.character_analysis is not None:
        render_analysis_preview(source, result.character_analysis, preview_path)

    pattern_path.write_text(result.render(), encoding="utf-8")
    export_strict_pattern(result.pattern_map, strict_path, result.crochet_pattern.title)
    export_stitch_graph(result.pattern_map, stitch_graph_path, result.crochet_pattern.title)
    render_stitch_simulation(result.pattern_map, simulation_path, result.crochet_pattern.title)
    details_path.write_text(_details_json(result, source, original_path, preview_path), encoding="utf-8")
    verification_path.write_text(_verification_json(result, strict_path, simulation_path, stitch_graph_path), encoding="utf-8")
    return destination


def export_planning_bundle(
    planning_result: PlanningResult,
    output_dir: str | Path,
    project_name: str = "amigurumi_planning_card",
    crochet_result: AppResult | None = None,
) -> Path:
    """Export the generated planning card, cleaned views, and model metadata."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_name(project_name)

    card_path = destination / f"{safe_name}_planning_card.jpg"
    shutil.copy2(planning_result.card_path, card_path)
    virtual_build_path = destination / f"{safe_name}_virtual_build.jpg"
    if planning_result.virtual_build_path and planning_result.virtual_build_path.exists():
        shutil.copy2(planning_result.virtual_build_path, virtual_build_path)
    design_proof_path = destination / f"{safe_name}_design_proof.jpg"
    if crochet_result is not None:
        render_design_proof(
            crochet_result.pattern_map,
            planning_result.model,
            design_proof_path,
            crochet_result.crochet_pattern.title,
        )
    accuracy_report_path = destination / f"{safe_name}_accuracy_report.json"
    clean_report_path = destination / f"{safe_name}_clean_report.html"
    accuracy_report = None
    if crochet_result is not None:
        accuracy_report = build_accuracy_report(planning_result, crochet_result, design_proof_path)
        accuracy_report_path.write_text(
            json.dumps(asdict(accuracy_report), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    model_path = destination / f"{safe_name}_planning_model.json"
    if planning_result.model_json_path and planning_result.model_json_path.exists():
        shutil.copy2(planning_result.model_json_path, model_path)

    views_dir = destination / f"{safe_name}_views"
    views_dir.mkdir(exist_ok=True)
    view_details = []
    for view in planning_result.model.views:
        suffix = "_inferred" if view.inferred else ""
        view_path = views_dir / f"{view.kind}{suffix}.png"
        shutil.copy2(view.cleaned_path, view_path)
        view_details.append(
            {
                "kind": view.kind,
                "source_path": str(view.source_path),
                "exported_path": str(view_path),
                "inferred": view.inferred,
                "confidence": view.confidence,
                "note": view.note,
            }
        )

    details = {
        "title": planning_result.model.title,
        "options": asdict(planning_result.model.options),
        "card_path": str(card_path),
        "virtual_build_path": str(virtual_build_path) if virtual_build_path.exists() else None,
        "design_proof_path": str(design_proof_path) if design_proof_path.exists() else None,
        "accuracy_report_path": str(accuracy_report_path) if accuracy_report_path.exists() else None,
        "clean_report_path": str(clean_report_path) if crochet_result is not None else None,
        "accuracy": asdict(accuracy_report) if accuracy_report is not None else None,
        "views": view_details,
        "shape_guides": [asdict(item) for item in planning_result.model.shape_guides],
        "proportions": [asdict(item) for item in planning_result.model.proportions],
        "construction": [asdict(item) for item in planning_result.model.construction],
        "parts": [asdict(item) for item in planning_result.model.parts],
        "details": [asdict(item) for item in planning_result.model.details],
        "uncertainties": [asdict(item) for item in planning_result.model.uncertainties],
        "compromises": [asdict(item) for item in planning_result.model.compromises],
        "warnings": list(planning_result.model.warnings),
        "structured_model": str(model_path) if model_path.exists() else None,
    }
    (destination / f"{safe_name}_planning_details.json").write_text(
        json.dumps(details, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if crochet_result is not None:
        export_clean_report(
            planning_result,
            crochet_result,
            clean_report_path,
            planning_card_path=card_path,
            virtual_build_path=virtual_build_path if virtual_build_path.exists() else None,
            design_proof_path=design_proof_path if design_proof_path.exists() else None,
            accuracy_report=accuracy_report,
        )
    return destination


def _details_json(
    result: AppResult,
    source: Path,
    original_path: Path,
    preview_path: Path,
) -> str:
    details = {
        "source_image": str(source),
        "exported_original": str(original_path),
        "exported_preview": str(preview_path) if preview_path.exists() else None,
        "qa_passed": result.qa_report.passed,
        "qa_issues": [asdict(issue) for issue in result.qa_report.issues],
        "voxel_model": asdict(result.voxel_model),
        "character_analysis": asdict(result.character_analysis) if result.character_analysis else None,
    }
    return json.dumps(details, indent=2, sort_keys=True)


def _verification_json(result: AppResult, strict_path: Path, simulation_path: Path, stitch_graph_path: Path) -> str:
    report = validate_pattern_map(result.pattern_map)
    graph_report = validate_stitch_graph(to_stitch_graph(result.pattern_map, result.crochet_pattern.title))
    details = {
        "passed": report.passed and graph_report.passed,
        "graph_passed": graph_report.passed,
        "graph_issues": [asdict(issue) for issue in graph_report.issues],
        "strict_pattern": str(strict_path),
        "stitch_simulation": str(simulation_path),
        "stitch_graph": str(stitch_graph_path),
        "issues": [asdict(issue) for issue in report.issues],
    }
    return json.dumps(details, indent=2, sort_keys=True)


def _safe_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip())
    return cleaned.strip("_") or "photo_to_pattern_plan"
