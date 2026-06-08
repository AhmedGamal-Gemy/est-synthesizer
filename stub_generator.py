import os

stubs = {
    "backend/app/scraper/gutenberg.py": [
        ("fetch_passages", "(n: int)", "Fetches n passages from Gutenberg."),
        ("parse_passage", "(html: str)", "Parses HTML content into a passage object.")
    ],
    "backend/app/scraper/processor.py": [
        ("compute_reading_level", "(text: str)", "Computes readability score."),
        ("tag_topics", "(text: str)", "Tags topics in the text."),
        ("is_suitable_for_est", "(passage: Passage) -> bool", "Checks suitability for EST.")
    ],
    "backend/app/generation/prompts.py": [
        ("build_system_prompt", "()", "Builds the LLM system prompt."),
        ("build_user_prompt", "(passage, few_shot_examples, slot_config) -> str", "Builds the user prompt.")
    ],
    "backend/app/generation/mistral.py": [
        ("MistralQueue", "", "Queue for Mistral API calls."),
        ("MistralQueue.submit", "(prompt, schema) -> dict", "Submits a prompt to the queue."),
        ("_call_with_retry", "(prompt) -> dict", "Calls Mistral API with retries.")
    ],
    "backend/app/generation/validator.py": [
        ("validate_question", "(output: MistralQuestionOutput, passage_text: str) -> tuple[bool, list[str]]", "Validates LLM output.")
    ],
    "backend/app/generation/loop.py": [
        ("run_generation_loop", "(blueprint, passages, few_shots, job_id) -> list[GeneratedQuestion]", "Runs generation loop.")
    ],
    "backend/app/generation/assembler.py": [
        ("assemble_test", "(questions, blueprint) -> GeneratedTest", "Assembles test.")
    ],
    "backend/app/pdf/renderer.py": [
        ("render_student_pdf", "(test: GeneratedTest) -> str", "Renders student PDF."),
        ("render_teacher_pdf", "(test: GeneratedTest) -> str", "Renders teacher PDF.")
    ],
    "backend/app/api/generate.py": [
        ("generate_test", "(job_id) -> dict", "POST /api/tests/generate endpoint.")
    ],
    "backend/app/api/progress.py": [
        ("get_progress", "(job_id) -> dict", "GET /api/tests/{job_id}/progress endpoint (SSE).")
    ],
    "backend/scripts/bootstrap_library.py": [
        ("main", "()", "Runs scraper -> processor -> qdrant.")
    ],
    "backend/scripts/generate_test.py": [
        ("main", "()", "Runs generation end-to-end.")
    ],
    "backend/tests/test_generation.py": [
        ("test_generation", "()", "Tests generation logic.")
    ]
}

for path, funcs in stubs.items():
    content = ""
    if "MistralQueue" in path:
        content = "class MistralQueue:\n"
    for func, args, doc in funcs:
        if "." in func:
            content += f"    def {func.split('.')[1]}{args}:\n        \"\"\"{doc}\"\"\"\n        raise NotImplementedError(\"{func.split('.')[1]} not implemented\")\n"
        else:
            content += f"def {func}{args}:\n    \"\"\"{doc}\"\"\"\n    raise NotImplementedError(\"{func} not implemented\")\n"
    
    with open(path.replace("/", "\\"), "w") as f:
        f.write(content)
