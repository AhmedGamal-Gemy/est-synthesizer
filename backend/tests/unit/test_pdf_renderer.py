"""Unit tests for backend.app.pdf.renderer."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from backend.app.pdf.renderer import (
    _render_html,
    _output_path,
    render_student_pdf,
    render_teacher_pdf,
)
from backend.app.schemas import (
    AnswerChoice,
    Difficulty,
    DistractorRole,
    GeneratedModule,
    GeneratedPassageBlock,
    GeneratedQuestion,
    GeneratedTest,
    ModuleType,
    SkillType,
)


# ponytail: skip PDF tests on platforms without the GTK3 runtime (Windows
# dev boxes without `scoop install gtk`). The HTML-only tests above still
# cover the rendering logic on every platform.
try:
    from weasyprint import HTML as _WP  # noqa: F401

    _WEASYPRINT_AVAILABLE = True
except OSError:
    _WEASYPRINT_AVAILABLE = False

skip_if_no_weasyprint = pytest.mark.skipif(
    not _WEASYPRINT_AVAILABLE,
    reason="WeasyPrint needs GTK3 runtime (libgobject); install via `scoop install gtk` on Windows or use Linux/macOS",
)


# ── Helpers ──────────────────────────────────────────────────


def _choice(letter: str, role: DistractorRole, text: str = "Choice text") -> AnswerChoice:
    return AnswerChoice(letter=letter, text=text, distractor_role=role)


def _question(qid: str, passage_id: str, module: int, slot: int, qnum: int) -> GeneratedQuestion:
    return GeneratedQuestion(
        id=qid,
        passage_id=passage_id,
        module_number=module,
        slot_number=slot,
        question_number=qnum,
        question_text="What does the passage say?",
        choices=[
            _choice("A", DistractorRole.BEST_ANSWER, "Best"),
            _choice("B", DistractorRole.GOOD_NOT_BEST, "Good"),
            _choice("C", DistractorRole.COMPLETELY_WRONG, "Wrong 1"),
            _choice("D", DistractorRole.COMPLETELY_WRONG, "Wrong 2"),
        ],
        correct_answer="A",
        explanation="Because the passage says so.",
        supporting_line="the passage says so",
        skill_type=SkillType.INFORMATION_AND_IDEAS,
        difficulty=Difficulty.MEDIUM,
    )


def _passage_block(pid: str, text: str, questions: list[GeneratedQuestion]) -> GeneratedPassageBlock:
    return GeneratedPassageBlock(
        passage_id=pid, passage_text=text, questions=questions
    )


def _fake_test() -> GeneratedTest:
    test_id = uuid.uuid4().hex[:12]
    job_id = uuid.uuid4().hex
    blueprint_id = uuid.uuid4().hex
    p1 = "p1"
    q1 = _question("q1", p1, 1, 1, 1)
    pb1 = _passage_block(p1, "The passage text.", [q1])
    mod1 = GeneratedModule(
        module_number=1,
        module_type=ModuleType.WRITING,
        passages=[pb1],
        questions=[q1],
        question_count=1,
    )
    return GeneratedTest(
        id=test_id,
        job_id=job_id,
        blueprint_id=blueprint_id,
        questions=[q1],
        modules=[mod1],
        total_questions=1,
    )


# ── HTML render tests (no PDF, no GTK needed) ───────────────


def test_render_html_student_omits_answer_key():
    test = _fake_test()
    html = _render_html(test, audience="student", passage_text={})
    assert "Best" in html
    # The explanation block is gated by `{% if audience == "teacher" %}` —
    # in student mode it must not appear at all
    assert "<strong>Answer:</strong>" not in html
    assert "Because the passage says so." not in html
    # The body class drives the mode
    assert 'class="student"' in html


def test_render_html_teacher_includes_explanation():
    test = _fake_test()
    html = _render_html(test, audience="teacher", passage_text={"p1": "Some passage."})
    assert "explanation" in html
    assert "Answer:" in html
    assert 'class="teacher"' in html
    assert "Some passage." in html


def test_render_html_uses_passage_text_overrides():
    test = _fake_test()
    html = _render_html(test, audience="student", passage_text={"p1": "Custom passage."})
    assert "Custom passage." in html


def test_render_html_missing_passage_renders_placeholder():
    test = _fake_test()
    html = _render_html(test, audience="student", passage_text={})
    assert "Passage text unavailable" in html


def test_render_html_includes_module_header():
    test = _fake_test()
    html = _render_html(test, audience="student", passage_text={})
    assert "Module 1" in html
    assert "Writing" in html


def test_render_html_sequences_question_numbers():
    p1, p2 = "p1", "p2"
    q1 = _question("q1", p1, 1, 1, 1)
    q2 = _question("q2", p1, 1, 1, 2)
    q3 = _question("q3", p2, 1, 1, 3)
    pb1 = _passage_block(p1, "P1 text.", [q1, q2])
    pb2 = _passage_block(p2, "P2 text.", [q3])
    mod = GeneratedModule(
        module_number=1, module_type=ModuleType.WRITING,
        passages=[pb1, pb2], questions=[q1, q2, q3], question_count=3,
    )
    test = GeneratedTest(
        id=uuid.uuid4().hex[:12], job_id="j", blueprint_id="b",
        questions=[q1, q2, q3], modules=[mod], total_questions=3,
    )
    html = _render_html(test, audience="student", passage_text={})
    assert 'start="1"' in html  # first question block
    assert 'start="3"' in html  # second question block


# ── Output path tests ────────────────────────────────────────


def test_output_path_uses_settings_dir(monkeypatch):
    test = _fake_test()
    path = _output_path(test, "student")
    assert path.name == f"test_{test.id}_student.pdf"
    # Default settings.GENERATED_PDF_PATH = "data/generated/"
    assert "data/generated" in str(path) or "generated" in str(path)


# ── PDF render tests (require WeasyPrint + GTK) ──────────────
# These tests need GTK3 runtime (libgobject). On Windows, install via
# `scoop install gtk` or run on Linux. They are marked as expected to fail
# in environments without GTK — the HTML tests above exercise the rendering
# logic without needing PDF output.


@skip_if_no_weasyprint
def test_render_student_pdf(tmp_path, monkeypatch):
    """Smoke test: render a fake test and verify a PDF was written."""
    monkeypatch.setattr(
        "backend.app.pdf.renderer.settings.GENERATED_PDF_PATH", str(tmp_path)
    )
    test = _fake_test()
    pdf_path = render_student_pdf(test, passage_text={"p1": "P1."})
    assert Path(pdf_path).exists()
    assert Path(pdf_path).stat().st_size > 0
    # PDF magic header
    with open(pdf_path, "rb") as f:
        assert f.read(4) == b"%PDF"


@skip_if_no_weasyprint
def test_render_teacher_pdf(tmp_path, monkeypatch):
    """Smoke test: render teacher PDF with answer key."""
    monkeypatch.setattr(
        "backend.app.pdf.renderer.settings.GENERATED_PDF_PATH", str(tmp_path)
    )
    test = _fake_test()
    pdf_path = render_teacher_pdf(test, passage_text={"p1": "P1."})
    assert Path(pdf_path).exists()
    assert Path(pdf_path).stat().st_size > 0
    with open(pdf_path, "rb") as f:
        assert f.read(4) == b"%PDF"
