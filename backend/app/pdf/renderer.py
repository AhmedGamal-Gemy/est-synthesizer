"""
EST Synthesizer — PDF Renderer

Renders a :class:`GeneratedTest` to a printable PDF using Jinja2
for the HTML template and WeasyPrint for the PDF conversion.

Two flavours:
- ``render_student_pdf`` — student-facing, no answer key
- ``render_teacher_pdf`` — teacher-facing, correct answers + explanations shown

The teacher task T13 ships the static ``test.html`` / ``test.css``; this module
wraps them with the GeneratedTest data and writes the PDF.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.app.config import settings
from backend.app.schemas import GeneratedTest

# ponytail: WeasyPrint is lazy-imported inside _write_pdf so that pure-HTML
# tests (and code paths that only need the HTML) work in environments without
# the GTK3 runtime (e.g. Windows dev boxes without scoop install gtk).

log = structlog.get_logger(__name__)

# ponytail: one env, one template, one CSS — reloaded only on first call
_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env: Environment | None = None


def _get_env() -> Environment:
    global _env
    if _env is None:
        _env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
        )
    return _env


def _render_html(
    test: GeneratedTest,
    audience: str,
    passage_text: Mapping[str, str] | None,
) -> str:
    """Render the HTML body for the given test + audience."""
    template = _get_env().get_template("test.html")
    return template.render(
        test=test,
        audience=audience,
        passage_text=passage_text or {},
    )


def _write_pdf(html: str, output_path: Path) -> Path:
    from weasyprint import CSS, HTML  # lazy import — see module docstring

    output_path.parent.mkdir(parents=True, exist_ok=True)
    css_path = _TEMPLATE_DIR / "test.css"
    HTML(string=html, base_url=str(_TEMPLATE_DIR)).write_pdf(
        target=str(output_path),
        stylesheets=[CSS(filename=str(css_path))] if css_path.exists() else None,
    )
    return output_path


def _output_path(test: GeneratedTest, audience: str) -> Path:
    base = Path(settings.GENERATED_PDF_PATH)
    return base / f"test_{test.id}_{audience}.pdf"


def render_student_pdf(
    test: GeneratedTest,
    passage_text: Mapping[str, str] | None = None,
) -> str:
    """Render the student-facing PDF. Returns the file path."""
    html = _render_html(test, audience="student", passage_text=passage_text)
    path = _output_path(test, "student")
    _write_pdf(html, path)
    log.info("Rendered student PDF", path=str(path), test_id=test.id)
    return str(path)


def render_teacher_pdf(
    test: GeneratedTest,
    passage_text: Mapping[str, str] | None = None,
) -> str:
    """Render the teacher-facing PDF (with answer key). Returns the file path."""
    html = _render_html(test, audience="teacher", passage_text=passage_text)
    path = _output_path(test, "teacher")
    _write_pdf(html, path)
    log.info("Rendered teacher PDF", path=str(path), test_id=test.id)
    return str(path)
