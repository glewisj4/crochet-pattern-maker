"""Tkinter GUI for the Photo-to-Pattern prototype."""

from __future__ import annotations

import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from .accuracy import AccuracyReport, build_accuracy_report
from .app import AppResult, PhotoToPatternApp
from .exporter import export_plan_bundle, export_planning_bundle
from .geometric_math import GeometricConfig
from .planning import PlanningOrchestrator, PlanningResult
from .planning.models import PlanningOptions
from .preview import render_analysis_preview
from .verification import validate_pattern_map


class PhotoToPatternGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Photo-to-Pattern Amigurumi Maker")
        self.geometry("1180x760")
        self.minsize(980, 640)

        self.app = PhotoToPatternApp()
        self.planner = PlanningOrchestrator()
        self.target_height_var = tk.DoubleVar(value=8.0)
        self.gauge_var = tk.DoubleVar(value=4.0)
        self.head_scale_var = tk.DoubleVar(value=1.0)
        self.body_scale_var = tk.DoubleVar(value=1.0)
        self.limb_scale_var = tk.DoubleVar(value=1.0)
        self.detail_scale_var = tk.DoubleVar(value=1.0)
        self.reimagine_var = tk.BooleanVar(value=False)
        self.image_path: Path | None = None
        self.image_paths: list[Path] = []
        self.crochet_source_path: Path | None = None
        self.result: AppResult | None = None
        self.planning_result: PlanningResult | None = None
        self.accuracy_report: AccuracyReport | None = None
        self.preview_path: Path | None = None
        self.preview_image: ImageTk.PhotoImage | None = None

        self._build_layout()

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(self, padding=16)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.columnconfigure(0, weight=1)

        title = ttk.Label(sidebar, text="Photo-to-Pattern", font=("Segoe UI", 18, "bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 16))

        self.path_label = ttk.Label(sidebar, text="No images selected", wraplength=260)
        self.path_label.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        ttk.Button(sidebar, text="Upload 1-4 Images", command=self.select_image).grid(row=2, column=0, sticky="ew", pady=4)
        self.analyze_button = ttk.Button(sidebar, text="Process Design", command=self.analyze)
        self.analyze_button.grid(row=3, column=0, sticky="ew", pady=4)
        self.export_button = ttk.Button(sidebar, text="Export Plans", command=self.export, state="disabled")
        self.export_button.grid(row=4, column=0, sticky="ew", pady=4)

        settings = ttk.LabelFrame(sidebar, text="Size & Proportions", padding=10)
        settings.grid(row=5, column=0, sticky="ew", pady=(14, 0))
        settings.columnconfigure(1, weight=1)
        _number_control(settings, "Height in", self.target_height_var, 0, 2.0, 36.0, 0.5)
        _number_control(settings, "Gauge sts/in", self.gauge_var, 1, 1.0, 10.0, 0.25)
        _number_control(settings, "Head scale", self.head_scale_var, 2, 0.5, 1.8, 0.05)
        _number_control(settings, "Body scale", self.body_scale_var, 3, 0.5, 1.8, 0.05)
        _number_control(settings, "Limb scale", self.limb_scale_var, 4, 0.5, 1.8, 0.05)
        _number_control(settings, "Detail scale", self.detail_scale_var, 5, 0.5, 1.8, 0.05)
        ttk.Checkbutton(
            settings,
            text="Re-imagine as amigurumi first",
            variable=self.reimagine_var,
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 0))

        self.status = ttk.Label(sidebar, text="Select 1 to 4 images to begin.", wraplength=260)
        self.status.grid(row=6, column=0, sticky="ew", pady=(18, 4))
        self.phase = ttk.Label(sidebar, text="Phase: idle", wraplength=260)
        self.phase.grid(row=7, column=0, sticky="ew", pady=(0, 6))
        self.progress = ttk.Progressbar(sidebar, mode="indeterminate")
        self.progress.grid(row=8, column=0, sticky="ew", pady=(0, 8))

        details = ttk.LabelFrame(sidebar, text="Detected Details", padding=10)
        details.grid(row=9, column=0, sticky="nsew", pady=(12, 0))
        sidebar.rowconfigure(9, weight=1)
        self.details_text = tk.Text(details, width=34, height=18, wrap="word", state="disabled")
        self.details_text.grid(row=0, column=0, sticky="nsew")
        details.rowconfigure(0, weight=1)
        details.columnconfigure(0, weight=1)

        main = ttk.Frame(self, padding=(0, 16, 16, 16))
        main.grid(row=0, column=1, sticky="nsew")
        main.rowconfigure(1, weight=1)
        main.columnconfigure(0, weight=1)

        ttk.Label(main, text="Preview", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        preview_frame = ttk.Frame(main, relief="groove", padding=8)
        preview_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 12))
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        self.preview_label = ttk.Label(preview_frame, text="Planning card will appear after upload.", anchor="center")
        self.preview_label.grid(row=0, column=0, sticky="nsew")

        pattern_frame = ttk.LabelFrame(main, text="Generated Pattern / Planning Notes", padding=8)
        pattern_frame.grid(row=2, column=0, sticky="ew")
        pattern_frame.columnconfigure(0, weight=1)
        self.pattern_text = tk.Text(pattern_frame, height=9, wrap="word", state="disabled")
        self.pattern_text.grid(row=0, column=0, sticky="ew")

    def select_image(self) -> None:
        selected = filedialog.askopenfilenames(
            title="Choose 1 to 4 Images",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("All files", "*.*"),
            ],
        )
        if not selected:
            return
        if len(selected) > 4:
            messagebox.showinfo("Too many images", "Choose no more than 4 images: front, side, back, and top.")
            return
        self.image_paths = [Path(path) for path in selected]
        self.image_path = self.image_paths[0]
        self.crochet_source_path = self.image_path
        self.result = None
        self.planning_result = None
        self.accuracy_report = None
        self.preview_path = None
        self.export_button.configure(state="disabled")
        self.path_label.configure(text="\n".join(str(path) for path in self.image_paths))
        self.status.configure(text="Images selected. Adjust settings, then click Process Design.")
        self.phase.configure(text="Phase: ready")
        self._set_text(self.details_text, "")
        self._set_text(self.pattern_text, "")
        self._show_source_preview(self.image_path)

    def analyze(self) -> None:
        if not self.image_paths:
            messagebox.showinfo("Select images", "Choose 1 to 4 images before generating a card.")
            return
        image_paths = list(self.image_paths)
        image_path = self.image_path
        title = image_path.stem if image_path else "Amigurumi Plan"
        options = self._planning_options()
        self.status.configure(text="Processing design...")
        self.phase.configure(text="Phase: starting")
        self.analyze_button.configure(state="disabled")
        self.export_button.configure(state="disabled")
        self.progress.start(12)
        threading.Thread(target=self._analyze_worker, args=(image_paths, image_path, title, options), daemon=True).start()

    def _analyze_worker(
        self,
        image_paths: list[Path],
        image_path: Path | None,
        title: str,
        options: PlanningOptions,
    ) -> None:
        try:
            planning_result = self.planner.create_from_images(
                image_paths,
                title=title,
                options=options,
                status_callback=self._set_phase_threadsafe,
            )
            self._set_phase_threadsafe("Generating final crochet rounds")
            crochet_source = _crochet_source_from_plan(planning_result) or image_path
            app = PhotoToPatternApp(_geometric_config_for_target(crochet_source, options))
            result = app.from_image_with_plan(crochet_source, planning_result.model, title=title)
            self._set_phase_threadsafe("Evaluating accuracy")
            accuracy_report = build_accuracy_report(planning_result, result)
            self._set_phase_threadsafe("Rendering annotated preview")
            preview_path = Path.cwd() / f"{title}_gui_preview.jpg"
            if result.character_analysis is not None:
                render_analysis_preview(crochet_source, result.character_analysis, preview_path)
            self.after(0, lambda: self._analysis_done(result, preview_path, planning_result, accuracy_report, crochet_source))
        except Exception as exc:
            self.after(0, lambda error=exc: self._analysis_failed(error))

    def _analysis_done(
        self,
        result: AppResult,
        preview_path: Path,
        planning_result: PlanningResult,
        accuracy_report: AccuracyReport,
        crochet_source: Path | None,
    ) -> None:
        self.result = result
        self.planning_result = planning_result
        self.accuracy_report = accuracy_report
        self.crochet_source_path = crochet_source
        self.preview_path = preview_path if preview_path.exists() else None
        self.analyze_button.configure(state="normal")
        self.export_button.configure(state="normal")
        self.progress.stop()
        accuracy_status = f"Accuracy {_percent(accuracy_report.overall_score)}"
        self.status.configure(text=f"Planning card and virtual build complete. {accuracy_status}. Review, then export plans.")
        self.phase.configure(text="Phase: complete")
        self._set_text(self.pattern_text, _planning_summary(planning_result, accuracy_report) + _verification_summary(result) + "\n\n" + result.render())
        self._set_text(self.details_text, _details_summary(result, planning_result, accuracy_report))
        self._show_source_preview(planning_result.card_path)

    def _analysis_failed(self, exc: Exception) -> None:
        self.analyze_button.configure(state="normal")
        self.progress.stop()
        self.status.configure(text="Analysis failed.")
        self.phase.configure(text="Phase: failed")
        messagebox.showerror("Analysis failed", str(exc))

    def export(self) -> None:
        if self.result is None or self.image_path is None or self.planning_result is None:
            messagebox.showinfo("Generate first", "Generate a planning card before exporting.")
            return
        selected = filedialog.askdirectory(title="Choose Export Folder")
        if not selected:
            return
        export_dir = export_plan_bundle(self.result, self.crochet_source_path or self.image_path, selected, project_name=self.image_path.stem)
        export_planning_bundle(self.planning_result, export_dir, project_name=self.image_path.stem, crochet_result=self.result)
        self.status.configure(text=f"Exported plans to {export_dir}")
        messagebox.showinfo("Export complete", f"Plans exported to:\n{export_dir}")

    def _show_source_preview(self, path: Path) -> None:
        image = Image.open(path).convert("RGB")
        image.thumbnail((820, 470))
        self.preview_image = ImageTk.PhotoImage(image)
        self.preview_label.configure(image=self.preview_image, text="")

    def _planning_options(self) -> PlanningOptions:
        return PlanningOptions(
            target_height_inches=max(2.0, self.target_height_var.get()),
            stitches_per_inch=max(1.0, self.gauge_var.get()),
            head_scale=max(0.5, self.head_scale_var.get()),
            body_scale=max(0.5, self.body_scale_var.get()),
            limb_scale=max(0.5, self.limb_scale_var.get()),
            detail_scale=max(0.5, self.detail_scale_var.get()),
            reimagine_as_amigurumi=self.reimagine_var.get(),
        )

    def _set_phase_threadsafe(self, message: str) -> None:
        self.after(0, lambda: self.phase.configure(text=f"Phase: {message}"))

    @staticmethod
    def _set_text(widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")


def _details_summary(
    result: AppResult,
    planning_result: PlanningResult | None = None,
    accuracy_report: AccuracyReport | None = None,
) -> str:
    lines = []
    if planning_result is not None:
        lines.append("Planning views:")
        for view in planning_result.model.views:
            marker = "AI/local inferred" if view.inferred else "uploaded"
            lines.append(f"- {view.kind}: {marker}, confidence {view.confidence:.2f}")
        lines.append("")
    analysis = result.character_analysis
    if analysis is not None:
        lines.append(f"Image size: {analysis.image_size[0]} x {analysis.image_size[1]}")
        x, y, width, height = analysis.foreground_bbox
        lines.append(f"Foreground: {width} x {height} at {x}, {y}")
        lines.append("")
        for region in analysis.regions:
            if region.kind == "unknown":
                continue
            rx, ry, rw, rh = region.bbox
            lines.append(f"{region.kind}: {rw} x {rh} at {rx}, {ry}")
    lines.append("")
    lines.append("QA:")
    if result.qa_report.issues:
        for issue in result.qa_report.issues:
            lines.append(f"- {issue.severity}: {issue.message}")
    else:
        lines.append("- Passed with no issues.")
    if accuracy_report is not None:
        lines.append("")
        lines.append("Accuracy:")
        lines.append(f"- Overall: {_percent(accuracy_report.overall_score)}")
        lines.append(f"- Input views: {_percent(accuracy_report.input_view_score)}")
        lines.append(f"- Planning model: {_percent(accuracy_report.planning_model_score)}")
        lines.append(f"- Crochet feasibility: {_percent(accuracy_report.crochet_feasibility_score)}")
        lines.append(f"- Virtual build/proof: {_percent(accuracy_report.virtual_build_score)}")
    return "\n".join(lines)


def _planning_summary(planning_result: PlanningResult, accuracy_report: AccuracyReport | None = None) -> str:
    lines = [f"Planning card: {planning_result.card_path}", ""]
    if planning_result.model_json_path:
        lines.append(f"Structured model: {planning_result.model_json_path}")
        lines.append("")
    if planning_result.virtual_build_path:
        lines.append(f"Virtual build: {planning_result.virtual_build_path}")
        lines.append("")
    lines.append("Design proof is generated during export as *_design_proof.jpg.")
    lines.append("")
    if planning_result.model.parts:
        lines.append("Design parts:")
        for part in planning_result.model.parts:
            lines.append(f"- {part.name}: {part.primitive}, attach {part.attachment}, confidence {part.confidence:.2f}")
        lines.append("")
    lines.append("Construction pieces:")
    for piece in planning_result.model.construction:
        lines.append(f"- {piece.name} x{piece.quantity}: {piece.primitive} ({piece.round_hint})")
    if planning_result.model.warnings:
        lines.append("")
        lines.append("Planning warnings:")
        for warning in planning_result.model.warnings:
            lines.append(f"- {warning}")
    if planning_result.model.uncertainties:
        lines.append("")
        lines.append("Review checkpoints:")
        for issue in planning_result.model.uncertainties:
            lines.append(f"- {issue.field}: {issue.recommendation}")
    if planning_result.model.compromises:
        lines.append("")
        lines.append("Form compromises:")
        for compromise in planning_result.model.compromises[:8]:
            lines.append(f"- {compromise.feature}: {compromise.crochet_treatment}")
    if accuracy_report is not None:
        lines.append("")
        lines.append(accuracy_report.render())
    return "\n".join(lines)


def _verification_summary(result: AppResult) -> str:
    report = validate_pattern_map(result.pattern_map)
    lines = ["", "Strict pattern verification:"]
    lines.append("- Passed" if report.passed else "- Needs review")
    for issue in report.issues[:6]:
        scope = issue.primitive_id
        if issue.round_number is not None:
            scope += f" R{issue.round_number}"
        lines.append(f"- {issue.severity}: {scope}: {issue.message}")
    return "\n".join(lines)


def _number_control(
    parent: ttk.Frame,
    label: str,
    variable: tk.DoubleVar,
    row: int,
    from_: float,
    to: float,
    increment: float,
) -> None:
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
    control = ttk.Spinbox(
        parent,
        from_=from_,
        to=to,
        increment=increment,
        textvariable=variable,
        width=8,
        justify="right",
    )
    control.grid(row=row, column=1, sticky="ew", pady=2)


def _geometric_config_for_target(image_path: Path | None, options: PlanningOptions) -> GeometricConfig:
    if image_path is None:
        return GeometricConfig()
    try:
        image = Image.open(image_path).convert("RGBA")
        bbox = image.getchannel("A").getbbox()
        source_height = (bbox[3] - bbox[1]) if bbox else image.height
    except Exception:
        source_height = 160
    target_stitches_high = max(8.0, options.target_height_inches * options.stitches_per_inch)
    stitch_width_px = max(1.0, source_height / target_stitches_high)
    return GeometricConfig(stitch_width_px=stitch_width_px)


def _crochet_source_from_plan(planning_result: PlanningResult) -> Path | None:
    front = next((view for view in planning_result.model.views if view.kind == "front"), None)
    return front.cleaned_path if front is not None else None


def _percent(value: float) -> str:
    return f"{round(max(0.0, min(1.0, value)) * 100):d}%"


def main() -> int:
    PhotoToPatternGUI().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
