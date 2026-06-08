def build_system_prompt():
    """Builds the LLM system prompt."""
    raise NotImplementedError("build_system_prompt not implemented")
def build_user_prompt(passage, few_shot_examples, slot_config) -> str:
    """Builds the user prompt."""
    raise NotImplementedError("build_user_prompt not implemented")
