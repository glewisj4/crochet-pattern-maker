"""Orchestrate multi-image planning-card creation."""

from __future__ import annotations

from pathlib import Path
import time

from photo_to_pattern.image_regions import CharacterRegionAnalyzer

from .agent import HeuristicPlanningAgent, PlanningModelAgent, write_planning_model_json
from .background import normalize_canvas, remove_background
from .card_renderer import render_planning_card
from .contact_sheet import looks_like_orthographic_contact_sheet, split_orthographic_contact_sheet
from .models import PlanningOptions, PlanningResult, PlanningView, ViewKind
from .reimaginer import AmigurumiReimaginer
from .view_classifier import classify_view
from .view_synthesizer import ViewSynthesizer
from .virtual_build import render_virtual_build


class PlanningOrchestratorAgent:
    """Orchestrator agent for multi-image amigurumi planning-card creation."""

    def __init__(
        self,
        work_root: str | Path | None = None,
        synthesizer: ViewSynthesizer | None = None,
        analyzer: CharacterRegionAnalyzer | None = None,
        model_agent: PlanningModelAgent | None = None,
        reimaginer: AmigurumiReimaginer | None = None,
    ) -> None:
        self.work_root = Path(work_root) if work_root else Path.cwd() / "planning_output"
        self.synthesizer = synthesizer or ViewSynthesizer()
        self.analyzer = analyzer or CharacterRegionAnalyzer()
        self.model_agent = model_agent or HeuristicPlanningAgent()
        self.reimaginer = reimaginer or AmigurumiReimaginer()

    def create_from_images(
        self,
        image_paths: list[str | Path],
        title: str | None = None,
        options: PlanningOptions | None = None,
        status_callback: object | None = None,
    ) -> PlanningResult:
        if not 1 <= len(image_paths) <= 4:
            raise ValueError("Upload between 1 and 4 images.")
        options = options or PlanningOptions()

        _status(status_callback, "Preparing workspace")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_title = _safe_name(title or Path(image_paths[0]).stem or "amigurumi_plan")
        work_dir = self.work_root / f"{safe_title}_{timestamp}"
        cleaned_dir = work_dir / "cleaned_views"
        contact_sheet_dir = work_dir / "contact_sheet_views"
        inferred_dir = work_dir / "inferred_views"
        reimagined_dir = work_dir / "reimagined_views"
        cleaned_dir.mkdir(parents=True, exist_ok=True)
        contact_sheet_dir.mkdir(parents=True, exist_ok=True)
        inferred_dir.mkdir(parents=True, exist_ok=True)
        reimagined_dir.mkdir(parents=True, exist_ok=True)

        source_paths = list(image_paths)
        _status(status_callback, "Checking for orthographic contact sheet")
        source_paths = self._expand_contact_sheet(source_paths, contact_sheet_dir, status_callback)
        if options.reimagine_as_amigurumi:
            _status(status_callback, "Re-imagining uploads as amigurumi-friendly references")
            source_paths = self._reimagine_sources(source_paths, reimagined_dir, status_callback)
        _status(status_callback, "Removing backgrounds and classifying views")
        views = self._prepare_uploaded_views(source_paths, cleaned_dir, status_callback)
        _status(status_callback, "Inferring missing front/side/back/top views")
        views = self._fill_missing_views(views, inferred_dir, status_callback)
        front = _view(views, "front") or views[0]
        _status(status_callback, "Analyzing character regions")
        analysis = self.analyzer.analyze(front.cleaned_path)
        _status(status_callback, "Building structured design model")
        model = self.model_agent.build_model(
            title=title or _display_title(front.source_path),
            options=options,
            views=tuple(views),
            analysis=analysis,
        )
        _status(status_callback, "Writing model JSON")
        model_json_path = write_planning_model_json(model, work_dir / f"{safe_title}_planning_model.json")
        _status(status_callback, "Rendering planning card")
        card_path = render_planning_card(model, work_dir / f"{safe_title}_planning_card.jpg")
        _status(status_callback, "Rendering virtual build")
        virtual_build_path = render_virtual_build(model, work_dir / f"{safe_title}_virtual_build.jpg")
        _status(status_callback, "Planning complete")
        return PlanningResult(
            model=model,
            card_path=card_path,
            work_dir=work_dir,
            model_json_path=model_json_path,
            virtual_build_path=virtual_build_path,
        )

    def _prepare_uploaded_views(
        self,
        image_paths: list[str | Path],
        cleaned_dir: Path,
        status_callback: object | None = None,
    ) -> list[PlanningView]:
        views: list[PlanningView] = []
        used: set[ViewKind] = set()
        for index, image_path in enumerate(image_paths, start=1):
            _status(status_callback, f"Cleaning upload {index} of {len(image_paths)}")
            source = Path(image_path)
            cleaned = cleaned_dir / f"upload_{index}_cleaned.png"
            normalized = cleaned_dir / f"upload_{index}_normalized.png"
            remove_background(source, cleaned)
            normalize_canvas(cleaned, normalized)
            kind, confidence, note = classify_view(normalized, used)
            if source.parent.name == "contact_sheet_views":
                sheet_kind = source.stem.replace("_view", "")
                if sheet_kind in {"front", "side", "back", "top"}:
                    kind = sheet_kind  # type: ignore[assignment]
                    confidence = 0.98
                    note = "extracted from one orthographic contact sheet"
            if kind != "unknown":
                used.add(kind)
            views.append(
                PlanningView(
                    kind=kind,
                    source_path=source,
                    cleaned_path=normalized,
                    inferred=False,
                    confidence=confidence,
                    note=note,
                )
            )
        return _dedupe_views(views)

    def _expand_contact_sheet(
        self,
        image_paths: list[str | Path],
        output_dir: Path,
        status_callback: object | None = None,
    ) -> list[Path | str]:
        if len(image_paths) != 1:
            return image_paths
        source = Path(image_paths[0])
        if not looks_like_orthographic_contact_sheet(source):
            return image_paths
        _status(status_callback, "Detected one-image orthographic sheet; splitting views")
        return split_orthographic_contact_sheet(source, output_dir)

    def _reimagine_sources(
        self,
        image_paths: list[str | Path],
        output_dir: Path,
        status_callback: object | None = None,
    ) -> list[Path]:
        reimagined: list[Path] = []
        for index, image_path in enumerate(image_paths, start=1):
            _status(status_callback, f"Re-imagining upload {index} of {len(image_paths)}")
            destination = output_dir / f"upload_{index}_amigurumi_reference.png"
            reimagined.append(self.reimaginer.reimagine(image_path, destination))
        return reimagined

    def _fill_missing_views(
        self,
        views: list[PlanningView],
        inferred_dir: Path,
        status_callback: object | None = None,
    ) -> list[PlanningView]:
        complete = list(views)
        present = {view.kind for view in complete}
        for kind in ("front", "side", "back", "top"):
            if kind in present:
                continue
            _status(status_callback, f"Inferring {kind} view")
            generated_path = inferred_dir / f"{kind}_inferred.png"
            complete.append(self.synthesizer.synthesize(kind, tuple(complete), generated_path))
            present.add(kind)
        return sorted(complete, key=lambda view: {"front": 0, "side": 1, "back": 2, "top": 3, "unknown": 4}[view.kind])

class PlanningOrchestrator(PlanningOrchestratorAgent):
    """Backward-compatible name for the planning orchestrator agent."""


def _dedupe_views(views: list[PlanningView]) -> list[PlanningView]:
    best: dict[ViewKind, PlanningView] = {}
    unknowns: list[PlanningView] = []
    for view in views:
        if view.kind == "unknown":
            unknowns.append(view)
            continue
        current = best.get(view.kind)
        if current is None or view.confidence > current.confidence:
            best[view.kind] = view
            if current is not None:
                unknowns.append(_as_unknown(current, "duplicate view kept as reference"))
        else:
            unknowns.append(_as_unknown(view, "duplicate view kept as reference"))
    return list(best.values()) + unknowns


def _as_unknown(view: PlanningView, note: str) -> PlanningView:
    return PlanningView(
        kind="unknown",
        source_path=view.source_path,
        cleaned_path=view.cleaned_path,
        inferred=view.inferred,
        confidence=view.confidence,
        note=note,
    )


def _view(views: tuple[PlanningView, ...] | list[PlanningView], kind: ViewKind) -> PlanningView | None:
    return next((view for view in views if view.kind == kind), None)


def _safe_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip())
    return cleaned.strip("_") or "amigurumi_plan"


def _display_title(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").title()


def _status(callback: object | None, message: str) -> None:
    if callable(callback):
        callback(message)
