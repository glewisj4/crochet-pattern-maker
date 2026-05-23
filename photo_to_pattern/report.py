"""Self-contained HTML report export for planning bundles."""

from __future__ import annotations

from base64 import b64encode
from dataclasses import asdict
from html import escape
from pathlib import Path
import mimetypes

from .accuracy import AccuracyReport
from .app import AppResult
from .planning import PlanningResult


def export_clean_report(
    planning_result: PlanningResult,
    crochet_result: AppResult,
    output_path: str | Path,
    *,
    planning_card_path: str | Path,
    virtual_build_path: str | Path | None = None,
    design_proof_path: str | Path | None = None,
    accuracy_report: AccuracyReport | None = None,
) -> Path:
    """Write a single-file HTML report with embedded CSS and images."""

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        build_clean_report_html(
            planning_result,
            crochet_result,
            planning_card_path=planning_card_path,
            virtual_build_path=virtual_build_path,
            design_proof_path=design_proof_path,
            accuracy_report=accuracy_report,
        ),
        encoding="utf-8",
    )
    return destination


def build_clean_report_html(
    planning_result: PlanningResult,
    crochet_result: AppResult,
    *,
    planning_card_path: str | Path,
    virtual_build_path: str | Path | None = None,
    design_proof_path: str | Path | None = None,
    accuracy_report: AccuracyReport | None = None,
) -> str:
    model = planning_result.model
    title = model.title or crochet_result.crochet_pattern.title
    accuracy_html = _accuracy_section(accuracy_report)
    image_panels = "\n".join(
        panel
        for panel in (
            _image_panel("Planning Card", planning_card_path),
            _image_panel("Virtual Build", virtual_build_path),
            _image_panel("Design Proof", design_proof_path),
        )
        if panel
    )

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{escape(title)} Clean Report</title>",
            f"<style>{_CSS}</style>",
            "</head>",
            "<body>",
            "<main>",
            "<header>",
            f"<p class=\"eyebrow\">Crochet Pattern Maker</p>",
            f"<h1>{escape(title)}</h1>",
            f"<p>{escape(_summary_line(planning_result, crochet_result))}</p>",
            "</header>",
            '<section class="gallery">',
            image_panels,
            "</section>",
            accuracy_html,
            _process_steps_section(planning_result),
            _planning_model_section(planning_result),
            _pattern_section(crochet_result),
            "</main>",
            "</body>",
            "</html>",
        ]
    )


def _summary_line(planning_result: PlanningResult, crochet_result: AppResult) -> str:
    model = planning_result.model
    return (
        f"{len(model.views)} reference view(s), {len(model.parts)} planned part type(s), "
        f"{len(crochet_result.pattern_map.rounds)} generated pattern section(s)."
    )


def _image_panel(title: str, path: str | Path | None) -> str:
    if path is None:
        return ""
    artifact = Path(path)
    if not artifact.exists() or artifact.stat().st_size == 0:
        return ""
    return "\n".join(
        [
            '<figure class="image-panel">',
            f"<img alt=\"{escape(title)}\" src=\"{_image_data_uri(artifact)}\">",
            f"<figcaption>{escape(title)}</figcaption>",
            "</figure>",
        ]
    )


def _image_data_uri(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _accuracy_section(report: AccuracyReport | None) -> str:
    if report is None:
        return _section("Accuracy Summary", "<p>No accuracy report was generated for this export.</p>")
    score_items = [
        ("Overall", report.overall_score),
        ("Input views", report.input_view_score),
        ("Planning model", report.planning_model_score),
        ("Crochet feasibility", report.crochet_feasibility_score),
        ("Virtual build/proof", report.virtual_build_score),
    ]
    meters = "\n".join(
        f'<div class="meter"><span>{escape(label)}</span><strong>{_percent(score)}</strong></div>'
        for label, score in score_items
    )
    checks = "\n".join(
        f"<li><strong>{escape(check.name)}:</strong> {_percent(check.score)} - {escape(check.message)}</li>"
        for check in report.checks
    )
    issues = "\n".join(
        f"<li><strong>{escape(issue.severity)}:</strong> {escape(issue.area)} - {escape(issue.message)}</li>"
        for issue in report.issues[:12]
    )
    issue_block = f"<h3>Review Notes</h3><ul>{issues}</ul>" if issues else "<p>No review notes.</p>"
    body = "\n".join(
        [
            f'<p class="status">Status: {"passed" if report.passed else "needs review"}</p>',
            f'<div class="meters">{meters}</div>',
            f"<h3>Checks</h3><ul>{checks}</ul>",
            issue_block,
        ]
    )
    return _section("Accuracy Summary", body)


def _process_steps_section(planning_result: PlanningResult) -> str:
    model = planning_result.model
    steps = []
    for piece in model.construction:
        steps.append(
            f"<li><strong>{escape(piece.name)} x{piece.quantity}:</strong> "
            f"{escape(piece.primitive)} - {escape(piece.round_hint)}</li>"
        )
    if not steps:
        steps.append("<li>No construction steps were generated.</li>")
    if model.compromises:
        steps.append("<li><strong>Compromises:</strong> " + escape("; ".join(
            f"{item.feature}: {item.crochet_treatment}" for item in model.compromises
        )) + "</li>")
    if model.warnings:
        steps.append("<li><strong>Warnings:</strong> " + escape("; ".join(model.warnings)) + "</li>")
    return _section("Process Steps", f"<ol>{''.join(steps)}</ol>")


def _planning_model_section(planning_result: PlanningResult) -> str:
    model = planning_result.model
    parts = "\n".join(
        f"<li><strong>{escape(part.name)}:</strong> {escape(part.primitive)}, "
        f"{escape(part.attachment)}, confidence {part.confidence:.2f}</li>"
        for part in model.parts
    )
    details = "\n".join(
        f"<li><strong>{escape(detail.name)}:</strong> {escape(detail.method)} at "
        f"{escape(detail.placement)}, confidence {detail.confidence:.2f}</li>"
        for detail in model.details
    )
    proportions = "\n".join(
        f"<li><strong>{escape(item.label)}:</strong> {escape(item.value)}</li>"
        for item in model.proportions
    )
    body = "\n".join(
        [
            "<h3>Parts</h3>",
            f"<ul>{parts or '<li>No structural parts were listed.</li>'}</ul>",
            "<h3>Details</h3>",
            f"<ul>{details or '<li>No surface details were listed.</li>'}</ul>",
            "<h3>Proportions</h3>",
            f"<ul>{proportions or '<li>No proportion guide was listed.</li>'}</ul>",
        ]
    )
    return _section("Planning Model", body)


def _pattern_section(crochet_result: AppResult) -> str:
    pattern_text = crochet_result.render()
    qa = asdict(crochet_result.qa_report)
    qa_summary = f"QA passed: {qa.get('passed', False)}; issue count: {len(qa.get('issues', []))}."
    body = "\n".join(
        [
            f"<p>{escape(qa_summary)}</p>",
            f"<pre>{escape(pattern_text)}</pre>",
        ]
    )
    return _section("Generated Pattern", body)


def _section(title: str, body: str) -> str:
    return f"<section><h2>{escape(title)}</h2>{body}</section>"


def _percent(value: float) -> str:
    return f"{round(max(0.0, min(1.0, value)) * 100):d}%"


_CSS = """
:root {
  color-scheme: light;
  --ink: #202124;
  --muted: #5f6368;
  --line: #d9d4ca;
  --paper: #fffdf8;
  --band: #f4efe5;
  --accent: #1b6b63;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Arial, Helvetica, sans-serif;
  color: var(--ink);
  background: var(--paper);
  line-height: 1.45;
}
main {
  width: min(1120px, calc(100% - 32px));
  margin: 0 auto;
  padding: 32px 0 48px;
}
header, section {
  border-bottom: 1px solid var(--line);
  padding: 24px 0;
}
h1, h2, h3, p { margin-top: 0; }
h1 { font-size: 34px; margin-bottom: 10px; }
h2 { font-size: 24px; }
h3 { font-size: 17px; margin-bottom: 8px; }
.eyebrow {
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
}
.gallery {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}
.image-panel {
  margin: 0;
  border: 1px solid var(--line);
  background: #fff;
}
.image-panel img {
  display: block;
  width: 100%;
  height: auto;
}
figcaption {
  padding: 8px 10px;
  color: var(--muted);
  font-size: 13px;
}
.meters {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  margin: 12px 0 18px;
}
.meter {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  background: var(--band);
  border: 1px solid var(--line);
}
.status { font-weight: 700; }
ul, ol { padding-left: 22px; }
li + li { margin-top: 6px; }
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  padding: 16px;
  border: 1px solid var(--line);
  background: #fff;
  font-family: Consolas, "Courier New", monospace;
  font-size: 13px;
}
@media print {
  main { width: auto; padding: 0; }
  section { break-inside: avoid; }
}
"""
