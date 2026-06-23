"""Extract real EST test questions from PDF samples → few-shot JSON + PDF spec.

Primary source: EST-may-2023 (2).pdf — has answer keys for both Writing (Test I)
and Reading (Test II) sections, plus skill-distribution tables.

Secondary sources: other PDFs — extract structure without correct answers.

Output: JSON array of few-shot examples matching the format in
backend/app/generation/few_shot.py

This output also doubles as a spec for the PDF renderer — the per-question layout
structure (passage → questions → choices) mirrors the real EST format.
"""

import json, re, sys, os
from pathlib import Path
from collections import defaultdict

# ── en-dash used in PDF text ──
ENDASH = "\u2013"

# ── helpers ──

def _norm(s: str) -> str:
    """Collapse whitespace, strip."""
    return re.sub(r'\s+', ' ', s).strip()

def _get_pdf_text(pdf_path: str) -> str:
    """Open PDF with pymupdf and return all text concatenated."""
    import fitz
    doc = fitz.open(pdf_path)
    parts = []
    for i in range(doc.page_count):
        parts.append(doc[i].get_text())
    doc.close()
    return "\n".join(parts)


# ── answer keys ──

def _parse_answer_keys(full_text: str) -> tuple[dict[int, str], dict[int, str]]:
    """Return (writing_answers, reading_answers) as dicts of qnum→letter."""
    writing_answers: dict[int, str] = {}
    reading_answers: dict[int, str] = {}

    # Find all "Answer Key" sections
    for m in re.finditer(r'Answer Key\s*(\(Reading Section\))?\s*'
                         r'(.*?)(?=May 2023\s+Distribution Table|'
                         r'--- PAGE|\Z)', full_text, re.DOTALL):
        section = m.group(0)
        is_reading = 'Reading Section' in section
        target = reading_answers if is_reading else writing_answers
        for line in section.split('\n'):
            line = line.strip()
            mm = re.match(r'^(\d+)\.\s*([A-D])\s*$', line)
            if mm:
                target[int(mm.group(1))] = mm.group(2)
    return writing_answers, reading_answers


# ── skill mapping (hardcoded from PDF distribution tables) ──

WRITING_SKILLS: dict[str, list[int]] = {
    "COMMAND_OF_EVIDENCE":              [5, 9, 12, 15, 23, 31, 35, 39],
    "WORDS_IN_CONTEXT":                 [2, 8, 13, 14, 27, 33, 38, 42],
    "EXPRESSION_OF_IDEAS":              [1, 2, 5, 6, 8, 9, 12, 13, 14, 15,
                                         16, 19, 23, 24, 26, 27, 31, 33, 35,
                                         36, 38, 39, 40, 42],
    "STANDARD_ENGLISH_CONVENTIONS":     [3, 4, 7, 10, 11, 17, 18, 20, 21, 22,
                                         25, 28, 29, 30, 32, 34, 37, 41, 43, 44],
}
# Questions can belong to multiple skills; we pick the most specific one.
# Priority order (first match wins):
_WRITING_SKILL_PRIORITY = [
    "STANDARD_ENGLISH_CONVENTIONS",
    "COMMAND_OF_EVIDENCE",
    "WORDS_IN_CONTEXT",
    "EXPRESSION_OF_IDEAS",
]

READING_SKILLS: dict[str, list[int]] = {
    "COMMAND_OF_EVIDENCE":              [2, 6, 14, 17, 24, 30, 37, 41, 44, 50],
    "WORDS_IN_CONTEXT":                 [7, 8, 9, 11, 20, 22, 32, 34, 39, 45, 47],
    "EXPRESSION_OF_IDEAS_IN_LITERATURE":[1, 3, 4, 5, 10, 13, 23, 25, 27, 40, 43, 46],
}
_READING_SKILL_PRIORITY = [
    "COMMAND_OF_EVIDENCE",
    "WORDS_IN_CONTEXT",
    "EXPRESSION_OF_IDEAS_IN_LITERATURE",
]


def _writing_skill(qnum: int) -> str:
    for sk in _WRITING_SKILL_PRIORITY:
        if qnum in WRITING_SKILLS[sk]:
            return sk
    return "EXPRESSION_OF_IDEAS"


def _reading_skill(qnum: int) -> str:
    # Determine if passage is history/social-studies or science
    # Q11-32 = history, Q33-52 = science (from distribution table)
    for sk, qnums in READING_SKILLS.items():
        if qnum in qnums:
            return sk
    if 11 <= qnum <= 32:
        return "ANALYSIS_IN_HISTORY_SOCIAL_STUDIES"
    if 33 <= qnum <= 52:
        return "ANALYSIS_IN_SCIENCE"
    return "EXPRESSION_OF_IDEAS"


# ── shared choice parser ──

def _parse_choices(text: str) -> list[dict]:
    """Parse A/B/C/D choices from text. Returns [{'choice_letter','choice_text'}]."""
    choices = []
    for letter in ('A', 'B', 'C', 'D'):
        # Pattern: "A. text" or "A.  text" with possible newline before
        pat = re.compile(
            r'(?:^|\n)\s*' + letter + r'\.\s*(.*?)(?=\n\s*[B-Z]\.\s|\Z)',
            re.DOTALL
        )
        m = pat.search(text)
        if m:
            txt = _norm(m.group(1))
            choices.append({"choice_letter": letter, "choice_text": txt})
    return choices


# ── locate question blocks in a section ──

def _find_question_blocks(text: str, q_start: int, q_end: int) -> list[tuple[int, str]]:
    """Return [(qnum, block_text), ...] for all questions in [q_start, q_end].

    Handles both 'N. stem' and 'N.A. NO CHANGE' formats.
    """
    qset = set(range(q_start, q_end + 1))
    # Build pattern that matches 'N.' or 'N.A' at line start
    nums = '|'.join(str(n) for n in qset)
    # Find all candidate positions
    blocks: list[tuple[int, int, int]] = []  # (qnum, start_pos, end_pos)

    for m in re.finditer(
        r'(?:^|\n)\s*(?P<num>' + nums + r')\.(?P<letter>A\.)?\s*',
        text
    ):
        qnum = int(m.group('num'))
        if qnum not in qset:
            continue
        # If we already saw this number, skip duplicates (page-header collisions)
        if blocks and blocks[-1][0] == qnum:
            continue
        blocks.append((qnum, m.start(), m.end()))

    # Assign end positions (next block's start or end of text)
    result: list[tuple[int, str]] = []
    for idx, (qnum, start, _) in enumerate(blocks):
        end = blocks[idx + 1][1] if idx + 1 < len(blocks) else len(text)
        block = text[start:end].strip()
        result.append((qnum, block))
    return result


# ── writing section ──

def _parse_writing_section(full_text: str,
                           answers: dict[int, str]) -> list[dict]:
    """Parse Writing (Literacy Test I) passages and questions."""
    m = re.search(
        r'Questions\s+1.+?(?=EST I ' + ENDASH + r' Literacy Test II)',
        full_text, re.DOTALL
    )
    if not m:
        print("  WARNING: writing section boundary not found")
        return []
    wt = m.group(0)

    # Split on passage headers
    blocks = re.split(
        r'(Questions \d+' + ENDASH + r'\d+ are based on the following passage[.:])',
        wt
    )
    examples: list[dict] = []

    passage_num = 0
    i = 1
    while i < len(blocks):
        header = blocks[i]
        content = blocks[i + 1] if i + 1 < len(blocks) else ''
        i += 2
        passage_num += 1

        qr = re.search(r'(\d+)' + ENDASH + r'(\d+)', header)
        if not qr:
            continue
        qs, qe = int(qr.group(1)), int(qr.group(2))

        # Split passage text from questions
        qblocks = _find_question_blocks(content, qs, qe)
        if not qblocks:
            continue

        first_q_pos = content.find(qblocks[0][1][:20])  # approximate
        if first_q_pos < 0:
            first_q_pos = 0
        passage_text = content[:first_q_pos].strip() if first_q_pos > 0 else ''
        # Fallback: search for the first question text
        if not passage_text:
            for candidate_qnum, candidate_block in qblocks:
                idx = content.find(candidate_block[:30])
                if idx > 0:
                    passage_text = content[:idx].strip()
                    break

        for qnum, qblock in qblocks:
            q = _parse_one_writing_question(
                qnum, qblock, answers, passage_text
            )
            if q:
                examples.append({
                    "source": "EST-may-2023",
                    "date": "2023-05",
                    "field": "literacy_test_i",
                    "section": "writing",
                    "location": f"passage_{passage_num}",
                    "attendance": qe - qs + 1,
                    "passage_text": passage_text,
                    "module_type": "writing",
                    "skill_type": _writing_skill(qnum),
                    "difficulty": "MEDIUM",
                    **q,
                })

    return examples


def _parse_one_writing_question(
    qnum: int, block: str, answers: dict[int, str],
    passage_text: str
) -> dict | None:
    """Parse a single writing-format question."""
    # Strip leading "N." prefix only — keep "A." intact if it follows
    # "1.A. NO CHANGE" → "A. NO CHANGE"  (keeps choice A marker)
    # "5. To make..." → "To make..."     (stem text starts)
    block = re.sub(r'^\s*\d+\.\s*', '', block)

    # Find choice A marker
    m_a = re.search(r'(?:^|\n)\s*A\.\s*', block)
    if not m_a:
        # Try without space
        m_a = re.search(r'(?:^|\n)\s*A\.(?!\w)', block)
    if not m_a:
        return None

    stem = block[:m_a.start()].strip()
    choices_text = block[m_a.start():]
    stem = _norm(stem)

    choices = _parse_choices(choices_text)
    if not choices:
        return None

    correct = answers.get(qnum, 'A')

    # Build question_text
    if not stem:
        qt = "Which choice corrects the underlined portion?"
    else:
        qt = stem[0].upper() + stem[1:]
        if not qt.endswith('?'):
            qt += '?'

    return {
        "question_text": qt,
        "choices": [
            {**c, "is_correct": c["choice_letter"] == correct}
            for c in choices
        ],
        "correct_answer": correct,
    }


# ── reading section ──

def _parse_reading_section(full_text: str,
                           answers: dict[int, str]) -> list[dict]:
    """Parse Reading (Literacy Test II) passages and questions."""
    m = re.search(
        r'EST I ' + ENDASH + r' Literacy Test II\s*\n.*?(?=Answer Key)',
        full_text, re.DOTALL
    )
    if not m:
        print("  WARNING: reading section boundary not found")
        return []
    rt = m.group(0)

    # Split on passage headers: "The following ... passage is ..."
    blocks = re.split(
        r'(The following (?:edited )?passage[^.]*\.)',
        rt
    )
    examples: list[dict] = []

    i = 1
    while i < len(blocks):
        header = blocks[i]
        content = blocks[i + 1] if i + 1 < len(blocks) else ''
        i += 2

        # Find which passage number this is (1-based within reading section)
        # Get all question numbers in this block
        qblocks = _find_question_blocks(content, 1, 52)
        if not qblocks:
            continue

        first_qnum = qblocks[0][0]
        last_qnum = qblocks[-1][0]

        # Estimate passage text vs questions boundary
        first_block_start = content.find(qblocks[0][1][:30])
        if first_block_start > 0:
            passage_text = content[:first_block_start].strip()
        else:
            passage_text = content.strip()
            # Try to remove questions from passage_text
            for qn, qb in qblocks[:3]:
                idx = passage_text.find(qb[:30])
                if idx > 0:
                    passage_text = passage_text[:idx].strip()
                    break

        # Clean passage header
        full_passage = header + '\n' + passage_text if not passage_text.startswith(header) else passage_text

        for qnum, qblock in qblocks:
            q = _parse_one_reading_question(qnum, qblock, answers, full_passage)
            if q:
                examples.append({
                    "source": "EST-may-2023",
                    "date": "2023-05",
                    "field": "literacy_test_ii",
                    "section": "reading",
                    "location": "passage_1" if first_qnum < 11 else "passage_2" if first_qnum < 32 else "passage_3",
                    "attendance": 52,
                    "passage_text": full_passage,
                    "module_type": "reading",
                    "skill_type": _reading_skill(qnum),
                    "difficulty": "MEDIUM",
                    **q,
                })

    return examples


def _parse_one_reading_question(
    qnum: int, block: str, answers: dict[int, str],
    passage_text: str
) -> dict | None:
    """Parse a single reading-format question."""
    block = re.sub(r'^\s*\d+\.\s*', '', block)

    m_a = re.search(r'(?:^|\n)\s*A\.\s+', block)
    if not m_a:
        return None

    stem = _norm(block[:m_a.start()])
    choices_text = block[m_a.start():]

    choices = _parse_choices(choices_text)
    if not choices:
        return None

    correct = answers.get(qnum, 'A')

    qt = stem[0].upper() + stem[1:] if stem else ''
    if qt and not qt.endswith('?'):
        qt += '?'

    return {
        "question_text": qt,
        "choices": [
            {**c, "is_correct": c["choice_letter"] == correct}
            for c in choices
        ],
        "correct_answer": correct,
    }


# ── main ──

def main():
    samples_dir = Path("docs/est-samples")
    output_path = Path("data/generated/extracted_samples.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_examples: list[dict] = []

    may2023_path = samples_dir / "EST-may-2023 (2).pdf"
    if may2023_path.exists():
        print(f"Reading {may2023_path.name} ...", end=" ", flush=True)
        text = _get_pdf_text(str(may2023_path))
        print(f"{len(text)} chars")

        w_answers, r_answers = _parse_answer_keys(text)
        print(f"  Writing answer keys: {len(w_answers)}")
        print(f"  Reading answer keys: {len(r_answers)}")

        writing = _parse_writing_section(text, w_answers)
        print(f"  Writing examples: {len(writing)}")

        reading = _parse_reading_section(text, r_answers)
        print(f"  Reading examples: {len(reading)}")

        all_examples.extend(writing)
        all_examples.extend(reading)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_examples, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(all_examples)} examples to {output_path}")

    by_skill: dict[str, int] = defaultdict(int)
    for ex in all_examples:
        by_skill[ex["skill_type"]] += 1
    print("\nBy skill:")
    for sk, cnt in sorted(by_skill.items()):
        print(f"  {sk}: {cnt}")


if __name__ == "__main__":
    main()
