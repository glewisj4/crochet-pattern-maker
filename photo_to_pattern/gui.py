"""Tkinter GUI for the Photo-to-Pattern prototype."""

from __future__ import annotations

import dataclasses
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
        self.aesthetic_style_var = tk.StringVar(value="classic")
        self.image_path: Path | None = None
        self.image_paths: list[Path] = []
        self.crochet_source_path: Path | None = None
        self.result: AppResult | None = None
        self.planning_result: PlanningResult | None = None
        self.accuracy_report: AccuracyReport | None = None
        self.preview_path: Path | None = None
        self.preview_image: ImageTk.PhotoImage | None = None

        self._last_selected_part: str | None = None
        self.part_states: dict[str, dict] = {}
        self.bg_image_pil: Image.Image | None = None
        self.bg_image_tk: ImageTk.PhotoImage | None = None

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
        
        ttk.Label(settings, text="Aesthetic Style").grid(row=6, column=0, sticky="w", pady=2)
        self.aesthetic_style_combo = ttk.Combobox(
            settings,
            textvariable=self.aesthetic_style_var,
            values=["classic", "chibi", "kawaii"],
            state="readonly",
            width=12,
        )
        self.aesthetic_style_combo.grid(row=6, column=1, sticky="ew", pady=2)

        ttk.Checkbutton(
            settings,
            text="Re-imagine as amigurumi first",
            variable=self.reimagine_var,
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # Workspace Editing sub-panel
        self.workspace_frame = ttk.LabelFrame(sidebar, text="Workspace Editing", padding=10)
        self.workspace_frame.grid(row=6, column=0, sticky="ew", pady=(14, 0))
        self.workspace_frame.columnconfigure(1, weight=1)

        ttk.Label(self.workspace_frame, text="Part:").grid(row=0, column=0, sticky="w", pady=2)
        self.selected_part_var = tk.StringVar(value="None Selected")
        self.selected_part_combo = ttk.Combobox(self.workspace_frame, textvariable=self.selected_part_var, state="readonly")
        self.selected_part_combo.grid(row=0, column=1, sticky="ew", pady=2)
        self.selected_part_combo.bind("<<ComboboxSelected>>", self.on_combobox_change)

        ttk.Label(self.workspace_frame, text="Rotation:").grid(row=1, column=0, sticky="w", pady=2)
        self.rotation_var = tk.DoubleVar(value=0.0)
        self.rotation_slider = ttk.Scale(self.workspace_frame, from_=-180.0, to=180.0, variable=self.rotation_var, orient="horizontal")
        self.rotation_slider.grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(self.workspace_frame, text="Size Scale:").grid(row=2, column=0, sticky="w", pady=2)
        self.size_scale_var = tk.DoubleVar(value=1.0)
        self.size_scale_slider = ttk.Scale(self.workspace_frame, from_=0.5, to=2.0, variable=self.size_scale_var, orient="horizontal")
        self.size_scale_slider.grid(row=2, column=1, sticky="ew", pady=2)

        ttk.Label(self.workspace_frame, text="Yarn:").grid(row=3, column=0, sticky="w", pady=2)
        self.yarn_type_var = tk.StringVar(value="acrylic")
        self.yarn_type_combo = ttk.Combobox(self.workspace_frame, textvariable=self.yarn_type_var, values=["acrylic", "cotton", "wool", "velvet/chenille"], state="readonly")
        self.yarn_type_combo.grid(row=3, column=1, sticky="ew", pady=2)

        ttk.Label(self.workspace_frame, text="Color Hex:").grid(row=4, column=0, sticky="w", pady=2)
        self.color_hex_var = tk.StringVar(value="#e87e40")
        self.color_hex_entry = ttk.Entry(self.workspace_frame, textvariable=self.color_hex_var)
        self.color_hex_entry.grid(row=4, column=1, sticky="ew", pady=2)

        self.apply_changes_btn = ttk.Button(self.workspace_frame, text="Apply Changes", command=self.apply_workspace_changes)
        self.apply_changes_btn.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 2))

        self.status = ttk.Label(sidebar, text="Select 1 to 4 images to begin.", wraplength=260)
        self.status.grid(row=7, column=0, sticky="ew", pady=(18, 4))
        self.phase = ttk.Label(sidebar, text="Phase: idle", wraplength=260)
        self.phase.grid(row=8, column=0, sticky="ew", pady=(0, 6))
        self.progress = ttk.Progressbar(sidebar, mode="indeterminate")
        self.progress.grid(row=9, column=0, sticky="ew", pady=(0, 8))

        details_frame = ttk.LabelFrame(sidebar, text="Detected Details", padding=10)
        details_frame.grid(row=10, column=0, sticky="nsew", pady=(12, 0))
        sidebar.rowconfigure(10, weight=1)
        self.details_text = tk.Text(details_frame, width=34, height=18, wrap="word", state="disabled")
        self.details_text.grid(row=0, column=0, sticky="nsew")
        details_frame.rowconfigure(0, weight=1)
        details_frame.columnconfigure(0, weight=1)

        main = ttk.Frame(self, padding=(0, 16, 16, 16))
        main.grid(row=0, column=1, sticky="nsew")
        main.rowconfigure(1, weight=1)
        main.columnconfigure(0, weight=1)

        ttk.Label(main, text="Preview", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        preview_frame = ttk.Frame(main, relief="groove", padding=8)
        preview_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 12))
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)

        self.interactive_canvas = tk.Canvas(preview_frame, width=820, height=470, bg="white", highlightthickness=0)
        self.interactive_canvas.grid(row=0, column=0, sticky="nsew")

        # Bind mouse events to the canvas
        self.interactive_canvas.bind("<Button-1>", self.on_canvas_click)
        self.interactive_canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.interactive_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.interactive_canvas.bind("<Double-1>", self.on_canvas_click)

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
            result = app.from_image_with_plan(
                crochet_source,
                planning_result.model,
                title=title,
                virtual_build_path=planning_result.virtual_build_path,
            )
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
        
        self.initialize_part_states()
        
        bg_path = crochet_source or self.image_path
        if bg_path:
            self._show_source_preview(bg_path)

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
        self.bg_image_pil = image
        self.bg_image_tk = ImageTk.PhotoImage(image)
        self.redraw_canvas()

    def initialize_part_states(self) -> None:
        self.part_states = {}
        if not self.planning_result or not self.planning_result.model:
            return

        for part in self.planning_result.model.parts:
            pos = part.pose_position
            if pos == (0.0, 0.0, 0.0):
                name_lower = part.name.lower()
                if "head" in name_lower:
                    pos = (410.0, 130.0, 0.0)
                elif "body" in name_lower or "torso" in name_lower:
                    pos = (410.0, 270.0, 0.0)
                elif "arm" in name_lower:
                    pos = (320.0, 270.0, 0.0)
                elif "leg" in name_lower:
                    pos = (360.0, 390.0, 0.0)
                elif "ear" in name_lower:
                    pos = (330.0, 70.0, 0.0)
                elif "tail" in name_lower:
                    pos = (510.0, 330.0, 0.0)
                else:
                    pos = (410.0, 235.0, 0.0)

            self.part_states[part.name] = {
                "pose_position": pos,
                "rotation_degrees": part.rotation_degrees,
                "size_scale": 1.0,
                "yarn_type": part.yarn_type,
                "color_hex": part.color_hex,
                "original_relative_size": part.relative_size,
                "is_detail": False,
            }

        for detail in self.planning_result.model.details:
            pos = detail.pose_position
            if pos == (0.0, 0.0, 0.0):
                name_lower = detail.name.lower()
                if "eye" in name_lower:
                    pos = (410.0, 110.0, 0.0)
                elif "snout" in name_lower or "muzzle" in name_lower or "nose" in name_lower:
                    pos = (410.0, 150.0, 0.0)
                else:
                    pos = (410.0, 200.0, 0.0)

            self.part_states[detail.name] = {
                "pose_position": pos,
                "rotation_degrees": detail.rotation_degrees,
                "size_scale": 1.0,
                "yarn_type": detail.yarn_type,
                "color_hex": detail.color_hex,
                "original_relative_size": (1.0, 1.0, 1.0),
                "is_detail": True,
            }

        part_names = list(self.part_states.keys())
        self.selected_part_combo["values"] = part_names
        if part_names:
            self.selected_part_combo.set(part_names[0])
            self._last_selected_part = part_names[0]
            self.load_selected_part_state()

    def load_selected_part_state(self) -> None:
        name = self.selected_part_var.get()
        if name in self.part_states:
            state = self.part_states[name]
            self.rotation_var.set(state["rotation_degrees"])
            self.size_scale_var.set(state["size_scale"])
            self.yarn_type_combo.set(state["yarn_type"])
            self.color_hex_var.set(state["color_hex"])

    def on_combobox_change(self, event=None) -> None:
        if hasattr(self, "_last_selected_part") and self._last_selected_part in self.part_states:
            self.part_states[self._last_selected_part]["rotation_degrees"] = self.rotation_var.get()
            self.part_states[self._last_selected_part]["size_scale"] = self.size_scale_var.get()
            self.part_states[self._last_selected_part]["yarn_type"] = self.yarn_type_combo.get()
            self.part_states[self._last_selected_part]["color_hex"] = self.color_hex_var.get()

        name = self.selected_part_var.get()
        self._last_selected_part = name
        self.load_selected_part_state()
        self.redraw_canvas()

    def redraw_canvas(self) -> None:
        self.interactive_canvas.delete("all")

        if hasattr(self, "bg_image_tk") and self.bg_image_tk is not None:
            self.interactive_canvas.create_image(410, 235, image=self.bg_image_tk, anchor="center")
        else:
            self.interactive_canvas.create_text(410, 235, text="Upload an image to start posing", fill="gray")

        if not hasattr(self, "part_states") or not self.part_states:
            return

        for name, state in self.part_states.items():
            x, y, _ = state["pose_position"]
            scale = state["size_scale"]
            color_hex = state["color_hex"]

            orig_w, orig_h, _ = state["original_relative_size"]
            w = max(40.0, 150.0 * orig_w * scale)
            h = max(40.0, 150.0 * orig_h * scale)

            is_selected = (name == self.selected_part_var.get())
            outline_color = "red" if is_selected else "#333333"
            outline_width = 3 if is_selected else 1.5

            x0 = x - w / 2
            y0 = y - h / 2
            x1 = x + w / 2
            y1 = y + h / 2

            name_lower = name.lower()
            if "head" in name_lower or "body" in name_lower or "torso" in name_lower:
                self.interactive_canvas.create_oval(
                    x0, y0, x1, y1, fill=color_hex, outline=outline_color, width=outline_width
                )
            else:
                self.interactive_canvas.create_rectangle(
                    x0, y0, x1, y1, fill=color_hex, outline=outline_color, width=outline_width
                )

            self.interactive_canvas.create_text(
                x, y, text=name, fill="white" if is_selected else "black", font=("Segoe UI", 9, "bold")
            )

    def on_canvas_click(self, event: tk.Event) -> None:
        if not hasattr(self, "part_states") or not self.part_states:
            return

        mx, my = event.x, event.y
        clicked_part = None

        sorted_parts = sorted(
            self.part_states.items(),
            key=lambda item: (item[1]["is_detail"], item[1]["original_relative_size"][0] * item[1]["original_relative_size"][1]),
            reverse=False,
        )

        for name, state in sorted_parts:
            x, y, _ = state["pose_position"]
            scale = state["size_scale"]

            orig_w, orig_h, _ = state["original_relative_size"]
            w = max(40.0, 150.0 * orig_w * scale)
            h = max(40.0, 150.0 * orig_h * scale)

            if (x - w/2 <= mx <= x + w/2) and (y - h/2 <= my <= y + h/2):
                clicked_part = name
                break

        if clicked_part:
            self.selected_part_combo.set(clicked_part)
            self.on_combobox_change()

            state = self.part_states[clicked_part]
            self.dragged_part = clicked_part
            self.drag_start_x = mx
            self.drag_start_y = my
            self.drag_start_part_pos = state["pose_position"]

    def on_canvas_drag(self, event: tk.Event) -> None:
        if not hasattr(self, "dragged_part") or self.dragged_part is None:
            return

        mx, my = event.x, event.y
        dx = mx - self.drag_start_x
        dy = my - self.drag_start_y

        start_x, start_y, start_z = self.drag_start_part_pos
        new_x = start_x + dx
        new_y = start_y + dy

        name_lower = self.dragged_part.lower()
        if any(limb in name_lower for limb in ("arm", "leg", "ear", "tail")):
            parent_name = None
            if "ear" in name_lower:
                parent_name = next((name for name in self.part_states if "head" in name.lower()), None)
            else:
                parent_name = next((name for name in self.part_states if "body" in name.lower() or "torso" in name.lower()), None)

            if parent_name:
                parent_state = self.part_states[parent_name]
                parent_pos = parent_state["pose_position"]
                parent_scale = parent_state["size_scale"]
                parent_orig_w, parent_orig_h, _ = parent_state["original_relative_size"]
                parent_w = max(40.0, 150.0 * parent_orig_w * parent_scale)
                parent_h = max(40.0, 150.0 * parent_orig_h * parent_scale)

                from photo_to_pattern.planning.models import snap_part_to_parent
                snapped_pos = snap_part_to_parent((new_x, new_y, start_z), parent_pos, parent_w, parent_h)
                new_x, new_y, _ = snapped_pos

        self.part_states[self.dragged_part]["pose_position"] = (new_x, new_y, start_z)
        self.redraw_canvas()

    def on_canvas_release(self, event: tk.Event) -> None:
        self.dragged_part = None

    def apply_workspace_changes(self) -> None:
        if self.planning_result is None or self.crochet_source_path is None:
            messagebox.showinfo("No project loaded", "Please process a design before applying changes.")
            return

        self._save_current_selection_state()

        updated_parts = []
        from photo_to_pattern.planning.agent import _parse_hex_color

        for part in self.planning_result.model.parts:
            state = self.part_states[part.name]
            orig_w, orig_h, orig_d = state["original_relative_size"]
            s = state["size_scale"]
            new_size = (round(orig_w * s, 2), round(orig_h * s, 2), round(orig_d * s, 2))

            color_hex = state["color_hex"]
            color_rgb = _parse_hex_color(color_hex)

            updated_part = dataclasses.replace(
                part,
                pose_position=state["pose_position"],
                rotation_degrees=state["rotation_degrees"],
                relative_size=new_size,
                color=color_rgb,
                color_hex=color_hex,
                yarn_type=state["yarn_type"],
            )
            updated_parts.append(updated_part)

        updated_details = []
        for detail in self.planning_result.model.details:
            state = self.part_states[detail.name]
            color_hex = state["color_hex"]
            color_rgb = _parse_hex_color(color_hex)

            updated_detail = dataclasses.replace(
                detail,
                pose_position=state["pose_position"],
                rotation_degrees=state["rotation_degrees"],
                color=color_rgb,
                color_hex=color_hex,
                yarn_type=state["yarn_type"],
            )
            updated_details.append(updated_detail)

        updated_model = dataclasses.replace(
            self.planning_result.model,
            parts=tuple(updated_parts),
            details=tuple(updated_details),
        )
        self.planning_result = dataclasses.replace(
            self.planning_result,
            model=updated_model,
        )

        self.status.configure(text="Applying changes and regenerating pattern...")
        self.phase.configure(text="Phase: regenerating")
        self.progress.start(12)
        threading.Thread(target=self._apply_changes_worker, daemon=True).start()

    def _apply_changes_worker(self) -> None:
        try:
            crochet_source = self.crochet_source_path
            options = self._planning_options()
            title = self.image_path.stem if self.image_path else "Amigurumi Plan"

            app = PhotoToPatternApp(_geometric_config_for_target(crochet_source, options))
            result = app.from_image_with_plan(
                crochet_source,
                self.planning_result.model,
                title=title,
                virtual_build_path=self.planning_result.virtual_build_path,
            )

            self._set_phase_threadsafe("Evaluating accuracy")
            accuracy_report = build_accuracy_report(self.planning_result, result)

            self._set_phase_threadsafe("Rendering annotated preview")
            preview_path = Path.cwd() / f"{title}_gui_preview.jpg"
            if result.character_analysis is not None:
                render_analysis_preview(crochet_source, result.character_analysis, preview_path)

            self.after(0, lambda: self._apply_changes_done(result, preview_path, accuracy_report))
        except Exception as exc:
            self.after(0, lambda error=exc: self._analysis_failed(error))

    def _apply_changes_done(
        self,
        result: AppResult,
        preview_path: Path,
        accuracy_report: AccuracyReport,
    ) -> None:
        self.result = result
        self.accuracy_report = accuracy_report
        self.preview_path = preview_path if preview_path.exists() else None
        self.progress.stop()

        accuracy_status = f"Accuracy {_percent(accuracy_report.overall_score)}"
        self.status.configure(text=f"Workspace changes applied successfully! {accuracy_status}.")
        self.phase.configure(text="Phase: complete")

        self._set_text(
            self.pattern_text,
            _planning_summary(self.planning_result, accuracy_report)
            + _verification_summary(result)
            + "\n\n"
            + result.render(),
        )
        self._set_text(self.details_text, _details_summary(result, self.planning_result, accuracy_report))

        self.redraw_canvas()

    def _save_current_selection_state(self) -> None:
        sel = self.selected_part_var.get()
        if sel and sel in self.part_states:
            self.part_states[sel]["rotation_degrees"] = self.rotation_var.get()
            self.part_states[sel]["size_scale"] = self.size_scale_var.get()
            self.part_states[sel]["yarn_type"] = self.yarn_type_combo.get()
            self.part_states[sel]["color_hex"] = self.color_hex_var.get()

    def _planning_options(self) -> PlanningOptions:
        return PlanningOptions(
            target_height_inches=max(2.0, self.target_height_var.get()),
            stitches_per_inch=max(1.0, self.gauge_var.get()),
            head_scale=max(0.5, self.head_scale_var.get()),
            body_scale=max(0.5, self.body_scale_var.get()),
            limb_scale=max(0.5, self.limb_scale_var.get()),
            detail_scale=max(0.5, self.detail_scale_var.get()),
            reimagine_as_amigurumi=self.reimagine_var.get(),
            aesthetic_style=self.aesthetic_style_var.get(),
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
    if result.dashboard_snapshot is not None:
        lines.append("")
        lines.append("Physics dashboard:")
        lines.extend(result.dashboard_snapshot.render().splitlines())
    return "\n".join(lines)


def _planning_summary(planning_result: PlanningResult, accuracy_report: AccuracyReport | None = None) -> str:
    lines = [f"Planning card: {planning_result.card_path}", ""]
    if planning_result.model_json_path:
        lines.append(f"Structured model: {planning_result.model_json_path}")
        lines.append("")
    if planning_result.virtual_build_path:
        lines.append(f"Virtual build: {planning_result.virtual_build_path}")
        lines.append("")
    if hasattr(planning_result, "virtual_build_path") and planning_result.virtual_build_path and hasattr(planning_result, "model"):
        lines.append("Virtual build output is included in the runtime dashboard after generation.")
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
