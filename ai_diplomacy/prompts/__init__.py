# ai_diplomacy/prompts/__init__.py
from ai_diplomacy.prompt_utils import load_prompt

# Define the constants by loading them from the .txt files
SYSTEM_PROMPT_TEMPLATE = load_prompt("system_prompt.txt")
PLANNING_PROMPT_TEMPLATE = load_prompt("planning_instructions.txt")
NEGOTIATION_DIARY_PROMPT_TEMPLATE = load_prompt("negotiation_diary_prompt.txt")
ORDER_SUBMISSION_PROMPT_TEMPLATE = load_prompt("order_instructions.txt")
ORDER_DIARY_PROMPT_TEMPLATE = load_prompt("order_diary_prompt.txt")

# For POWER_SPECIFIC_PROMPTS, it's a dictionary.
POWER_SPECIFIC_PROMPTS = {
    "AUSTRIA": load_prompt("austria_system_prompt.txt"),
    "ENGLAND": load_prompt("england_system_prompt.txt"),
    "FRANCE": load_prompt("france_system_prompt.txt"),
    "GERMANY": load_prompt("germany_system_prompt.txt"),
    "ITALY": load_prompt("italy_system_prompt.txt"),
    "RUSSIA": load_prompt("russia_system_prompt.txt"),
    "TURKEY": load_prompt("turkey_system_prompt.txt"),
}

# Additional templates that might be used elsewhere or by agent.py implicitly
# via llm_utils.load_prompt_file if that function is also used directly by agent.py
# For now, only defining what agent.py explicitly imports from ai_diplomacy.prompts

__all__ = [
    "SYSTEM_PROMPT_TEMPLATE",
    "POWER_SPECIFIC_PROMPTS",
    "PLANNING_PROMPT_TEMPLATE",
    "NEGOTIATION_DIARY_PROMPT_TEMPLATE",
    "ORDER_SUBMISSION_PROMPT_TEMPLATE",
    "ORDER_DIARY_PROMPT_TEMPLATE",
]
