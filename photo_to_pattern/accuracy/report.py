"""Deterministic accuracy report for the current app pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from photo_to_pattern.app import AppResult
from photo_to_pattern.planning import PlanningResult
from photo_to_pattern.planning.models import DesignPart, PlanningModel
from photo_to_pattern.verification import validate_pattern_map, validate_stitch_graph
from photo_to_pattern.verification.stitch_graph import to_stitch_graph

AccuracySeverity = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class AccuracyIssue:
    severity: AccuracySeverity
    area: str
    message: str


@dataclass(frozen=True)
class AccuracyCheck:
    name: str
    score: float
    passed: bool
    message: str


@dataclass(frozen=True)
class AccuracyReport:
    overall_score: float
    input_view_score: float
    planning_model_score: float
    crochet_feasibility_score: float
    virtual_build_score: float
    passed: bool
    checks: tuple[AccuracyCheck, ...]
    issues: tuple[AccuracyIssue, ...]

    def render(self) -> str:
        lines = [
            "Accuracy Report",
            f"Overall: {_percent(self.overall_score)}",
            f"Input views: {_percent(self.input_view_score)}",
            f"Planning model: {_percent(self.planning_model_score)}",
            f"Crochet feasibility: {_percent(self.crochet_feasibility_score)}",
            f"Virtual build/proof: {_percent(self.virtual_build_score)}",
            "Status: passed" if self.passed else "Status: needs review",
            "",
            "Checks:",
        ]
        for check in self.checks:
            status = "passed" if check.passed else "review"
            lines.append(f"- {check.name}: {_percent(check.score)} ({status}) - {check.message}")
        if self.issues:
            lines.append("")
            lines.append("Accuracy issues:")
            for issue in self.issues[:12]:
                lines.append(f"- {issue.severity}: {issue.area}: {issue.message}")
        return "\n".join(lines)


def build_accuracy_report(
    planning_result: PlanningResult,
    crochet_result: AppResult,
    design_proof_path: str | Path | None = None,
) -> AccuracyReport:
    """Score how well the app can justify the generated design and pattern."""

    issues: list[AccuracyIssue] = []
    view_score, view_check = _score_input_views(planning_result, issues)
    planning_score, planning_check = _score_planning_model(planning_result.model, crochet_result, issues)
    feasibility_score, feasibility_check = _score_crochet_feasibility(crochet_result, issues)
    virtual_score, virtual_check = _score_virtual_build(planning_result, design_proof_path, issues)

    overall = _clamp(
        view_score * 0.25
        + planning_score * 0.25
        + feasibility_score * 0.35
        + virtual_score * 0.15
    )
    has_errors = any(issue.severity == "error" for issue in issues)
    passed = overall >= 0.75 and not has_errors
    return AccuracyReport(
        overall_score=overall,
        input_view_score=view_score,
        planning_model_score=planning_score,
        crochet_feasibility_score=feasibility_score,
        virtual_build_score=virtual_score,
        passed=passed,
        checks=(view_check, planning_check, feasibility_check, virtual_check),
        issues=tuple(issues),
    )


def _score_input_views(
    planning_result: PlanningResult,
    issues: list[AccuracyIssue],
) -> tuple[float, AccuracyCheck]:
    expected = ("front", "side", "back", "top")
    by_kind = {view.kind: view for view in planning_result.model.views}
    scores = []
    real_count = 0
    inferred_count = 0
    for kind in expected:
        view = by_kind.get(kind)
        if view is None:
            issues.append(AccuracyIssue("error", "input views", f"Missing {kind} view."))
            scores.append(0.0)
            continue
        if view.inferred:
            inferred_count += 1
            issues.append(AccuracyIssue("warning", "input views", f"{kind} view was inferred, not directly observed."))
        else:
            real_count += 1
        evidence_factor = 0.72 if view.inferred else 1.0
        scores.append(_clamp(view.confidence * evidence_factor))

    unknowns = [view for view in planning_result.model.views if view.kind == "unknown"]
    if unknowns:
        issues.append(AccuracyIssue("warning", "input views", f"{len(unknowns)} duplicate/unknown uploaded view(s) were not used as primary evidence."))

    score = sum(scores) / len(expected)
    message = f"{real_count} real view(s), {inferred_count} inferred view(s)."
    return score, AccuracyCheck("Input view evidence", score, score >= 0.75, message)


def _score_planning_model(
    model: PlanningModel,
    crochet_result: AppResult,
    issues: list[AccuracyIssue],
) -> tuple[float, AccuracyCheck]:
    expected_ids = _expected_structural_ids(model)
    generated_ids = {round_spec.primitive_id for round_spec in crochet_result.pattern_map.rounds}
    missing = sorted(expected_ids - generated_ids)
    coverage = 1.0 if not expected_ids else (len(expected_ids) - len(missing)) / len(expected_ids)
    if missing:
        issues.append(AccuracyIssue("error", "planning model", f"Missing generated rounds for: {', '.join(missing)}."))

    confidences = [part.confidence for part in model.parts]
    confidence_score = sum(confidences) / len(confidences) if confidences else 0.55
    shape_score = _shape_guide_score(model, issues)
    ambiguity_penalty = _reference_ambiguity_penalty(model, issues)
    distinctive_penalty = _distinctive_feature_penalty(model, issues)
    compromise_penalty = min(0.18, len(model.compromises) * 0.03)
    uncertainty_penalty = min(0.12, len(model.uncertainties) * 0.03)
    score = _clamp(
        coverage * 0.55
        + confidence_score * 0.25
        + shape_score * 0.20
        - compromise_penalty
        - uncertainty_penalty
        - ambiguity_penalty
        - distinctive_penalty
    )

    if model.compromises:
        issues.append(AccuracyIssue("info", "planning model", f"{len(model.compromises)} feature compromise(s) documented."))
    if model.uncertainties:
        issues.append(AccuracyIssue("warning", "planning model", f"{len(model.uncertainties)} planning uncertainty checkpoint(s) need review."))

    message = f"{len(expected_ids) - len(missing)}/{len(expected_ids)} structural generated part(s) covered."
    return score, AccuracyCheck("Planning model coverage", score, not missing and score >= 0.70, message)


def _score_crochet_feasibility(
    crochet_result: AppResult,
    issues: list[AccuracyIssue],
) -> tuple[float, AccuracyCheck]:
    pattern_report = validate_pattern_map(crochet_result.pattern_map)
    graph_report = validate_stitch_graph(to_stitch_graph(crochet_result.pattern_map, crochet_result.crochet_pattern.title))
    error_count = sum(1 for issue in pattern_report.issues if issue.severity == "error") + graph_report.error_count
    warning_count = sum(1 for issue in pattern_report.issues if issue.severity == "warning") + graph_report.warning_count
    for issue in pattern_report.issues[:8]:
        issues.append(AccuracyIssue(issue.severity, "crochet feasibility", f"{issue.primitive_id}: {issue.message}"))  # type: ignore[arg-type]
    for issue in graph_report.issues[:8]:
        issues.append(AccuracyIssue(issue.severity, "stitch graph", f"{issue.scope}: {issue.message}"))  # type: ignore[arg-type]

    score = _clamp(1.0 - error_count * 0.30 - warning_count * 0.06)
    passed = pattern_report.passed and graph_report.passed
    message = f"{error_count} error(s), {warning_count} warning(s) across strict pattern and stitch graph."
    return score, AccuracyCheck("Crochet feasibility", score, passed, message)


def _score_virtual_build(
    planning_result: PlanningResult,
    design_proof_path: str | Path | None,
    issues: list[AccuracyIssue],
) -> tuple[float, AccuracyCheck]:
    score = 0.0
    if _artifact_exists(planning_result.card_path):
        score += 0.25
    else:
        issues.append(AccuracyIssue("error", "proof artifacts", "Planning card image was not generated."))

    if _artifact_exists(planning_result.model_json_path):
        score += 0.20
    else:
        issues.append(AccuracyIssue("warning", "proof artifacts", "Structured planning model JSON was not generated."))

    if _artifact_exists(planning_result.virtual_build_path):
        score += 0.30
    else:
        issues.append(AccuracyIssue("warning", "virtual build", "Virtual build image was not generated."))

    if _artifact_exists(design_proof_path):
        score += 0.20
    else:
        issues.append(AccuracyIssue("info", "virtual build", "Design proof image is generated during export."))

    documented_tradeoffs = bool(planning_result.model.compromises or planning_result.model.uncertainties or planning_result.model.warnings)
    score += 0.05 if documented_tradeoffs else 0.03
    message = "Virtual build available; design proof available." if score >= 0.90 else "Virtual/proof artifacts are partially available."
    return _clamp(score), AccuracyCheck("Virtual build and proof artifacts", _clamp(score), score >= 0.70, message)


def _shape_guide_score(model: PlanningModel, issues: list[AccuracyIssue]) -> float:
    if not model.parts:
        issues.append(AccuracyIssue("warning", "planning model", "No design parts were detected."))
        return 0.0
    guide_names = {_normalize_id(guide.name) for guide in model.shape_guides}
    structural = [part for part in model.parts if _is_structural_part(part)]
    if not structural:
        return 0.55
    if not guide_names:
        issues.append(AccuracyIssue("warning", "planning model", "No shape-guide evidence is available for structural part matching."))
        return 0.55
    matched = 0
    for part in structural:
        part_id = _normalize_id(part.name)
        if any(part_id in guide or guide in part_id for guide in guide_names):
            matched += 1
    if matched == 0 and guide_names:
        issues.append(AccuracyIssue("warning", "planning model", "Shape guides exist but are not clearly mapped to named structural parts."))
        return 0.45
    if matched < len(structural):
        issues.append(
            AccuracyIssue(
                "warning",
                "planning model",
                f"Shape-guide evidence maps to {matched}/{len(structural)} structural part type(s).",
            )
        )
    return matched / len(structural)


def _reference_ambiguity_penalty(model: PlanningModel, issues: list[AccuracyIssue]) -> float:
    real_views = [view for view in model.views if view.kind != "unknown" and not view.inferred]
    low_confidence_views = [
        view.kind for view in model.views if view.kind != "unknown" and (view.inferred or view.confidence < 0.65)
    ]
    unknown_views = [view for view in model.views if view.kind == "unknown"]
    ambiguous_notes = [
        view.kind
        for view in model.views
        if _contains_any(view.note, ("ambiguous", "cropped", "partial", "occluded", "framing", "unclear", "duplicate"))
    ]

    penalty = 0.0
    if len(real_views) <= 1:
        issues.append(
            AccuracyIssue(
                "warning",
                "reference framing",
                "Only one direct reference view is available; side, back, or top details may be ambiguous.",
            )
        )
        penalty += 0.05
    if low_confidence_views:
        issues.append(
            AccuracyIssue(
                "warning",
                "reference ambiguity",
                f"Low-confidence or inferred view evidence affects: {', '.join(sorted(set(low_confidence_views)))}.",
            )
        )
        penalty += min(0.06, len(set(low_confidence_views)) * 0.02)
    if unknown_views:
        penalty += 0.02
    if ambiguous_notes:
        issues.append(
            AccuracyIssue(
                "warning",
                "reference framing",
                f"Reference notes indicate ambiguous framing for: {', '.join(sorted(set(ambiguous_notes)))}.",
            )
        )
        penalty += min(0.04, len(set(ambiguous_notes)) * 0.02)
    return min(0.12, penalty)


def _distinctive_feature_penalty(model: PlanningModel, issues: list[AccuracyIssue]) -> float:
    if not _has_low_confidence_defaults(model):
        return 0.0

    evidence_text = _model_text(model)
    planned_text = _details_and_construction_text(model)
    absent_features = [
        label
        for label, keywords, evidence_keywords in _DISTINCTIVE_FEATURE_KEYWORDS
        if _contains_any(evidence_text, evidence_keywords)
        if not _contains_any(planned_text, keywords)
    ]
    if not absent_features:
        return 0.0

    issues.append(
        AccuracyIssue(
            "warning",
            "distinctive features",
            "Low-confidence defaults are present, but these distinctive cues are absent from model details/construction: "
            + ", ".join(absent_features)
            + ".",
        )
    )
    return min(0.15, len(absent_features) * 0.03)


def _has_low_confidence_defaults(model: PlanningModel) -> bool:
    evidence_text = _model_text(model)
    if _contains_any(evidence_text, ("inferred default", "default", "fallback", "low confidence", "low-confidence")):
        return True
    if any(part.confidence < 0.45 for part in model.parts):
        return True
    if any(detail.confidence < 0.45 for detail in model.details):
        return True
    if len([view for view in model.views if view.kind != "unknown" and not view.inferred]) <= 1:
        return True
    return any(view.inferred or view.confidence < 0.65 for view in model.views if view.kind != "unknown")


def _model_text(model: PlanningModel) -> str:
    values: list[str] = [model.title]
    values.extend(view.note for view in model.views)
    values.extend(guide.name for guide in model.shape_guides)
    values.extend(guide.primitive for guide in model.shape_guides)
    values.extend(part.name for part in model.parts)
    values.extend(part.primitive for part in model.parts)
    values.extend(part.attachment for part in model.parts)
    values.extend(part.source for part in model.parts)
    values.extend(detail.name for detail in model.details)
    values.extend(detail.method for detail in model.details)
    values.extend(detail.placement for detail in model.details)
    values.extend(detail.source for detail in model.details)
    values.extend(piece.name for piece in model.construction)
    values.extend(piece.primitive for piece in model.construction)
    values.extend(piece.round_hint for piece in model.construction)
    values.extend(uncertainty.field for uncertainty in model.uncertainties)
    values.extend(uncertainty.reason for uncertainty in model.uncertainties)
    values.extend(uncertainty.recommendation for uncertainty in model.uncertainties)
    values.extend(compromise.feature for compromise in model.compromises)
    values.extend(compromise.original_treatment for compromise in model.compromises)
    values.extend(compromise.crochet_treatment for compromise in model.compromises)
    values.extend(compromise.reason for compromise in model.compromises)
    values.extend(model.warnings)
    return " ".join(value for value in values if value).lower()


def _details_and_construction_text(model: PlanningModel) -> str:
    values: list[str] = []
    values.extend(detail.name for detail in model.details)
    values.extend(detail.method for detail in model.details)
    values.extend(detail.placement for detail in model.details)
    values.extend(detail.source for detail in model.details)
    values.extend(piece.name for piece in model.construction)
    values.extend(piece.primitive for piece in model.construction)
    values.extend(piece.round_hint for piece in model.construction)
    return " ".join(value for value in values if value).lower()


def _contains_any(value: str, needles: tuple[str, ...]) -> bool:
    text = value.lower()
    return any(needle in text for needle in needles)


def _expected_structural_ids(model: PlanningModel) -> set[str]:
    ids = set()
    quantities = {piece.name: piece.quantity for piece in model.construction}
    for part in model.parts:
        if not _is_structural_part(part):
            continue
        base = _normalize_id(part.name)
        quantity = max(1, quantities.get(part.name, 1))
        if quantity == 1:
            ids.add(base)
        else:
            ids.update(f"{base}_{index}" for index in range(1, quantity + 1))
    return ids


def _is_structural_part(part: DesignPart) -> bool:
    primitive = part.primitive.lower()
    return not any(marker in primitive for marker in ("detail", "applique", "embroidery"))


def _normalize_id(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _percent(value: float) -> str:
    return f"{round(_clamp(value) * 100):d}%"


def _artifact_exists(path: str | Path | None) -> bool:
    if path is None:
        return False
    try:
        artifact = Path(path)
        return artifact.exists() and artifact.stat().st_size > 0
    except OSError:
        return False


_DISTINCTIVE_FEATURE_KEYWORDS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "leaf cloak",
        ("leaf cloak", "leaf cape", "leaf mantle", "leaf poncho", "leaf collar", "leaf wrap", "leaf body wrap"),
        ("leaf", "cloak", "cape", "mantle", "poncho", "wrap"),
    ),
    (
        "inner ears",
        ("inner ear", "inner-ear", "ear inset", "ear lining"),
        ("fox", "cat", "bunny", "rabbit", "bear", "ear"),
    ),
    (
        "snout/muzzle",
        ("snout", "muzzle"),
        ("fox", "cat", "bear", "dog", "muzzle", "snout", "face mask"),
    ),
    (
        "tail",
        ("tail",),
        ("fox", "cat", "dog", "tail"),
    ),
    (
        "embroidery",
        ("embroidery", "embroider", "embroidered"),
        ("embroider", "embroidery", "closed eye", "closed eyes", "vein", "face"),
    ),
)
