from typing import Dict, List, Tuple, Set, Optional # Added to resolve NameError: name 'List' is not defined
import os

def load_prompt(filename: str) -> str:
    """Load a prompt from a file located in the 'prompts' subdirectory
    relative to the current script file."""
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(current_script_dir, "prompts", filename)

    if not os.path.exists(filepath):
        # For debugging, let's also check the CWD based path as a fallback
        # as this was part of the original complex logic.
        # This helps understand if the script is being run from an unexpected CWD.
        cwd_path = os.path.join(os.getcwd(), "prompts", filename)
        
        # Also check project root based path (assuming prompt_utils.py is in ai_diplomacy/
        # and prompts/ is at the project root: <project_root>/prompts/)
        project_root_prompts_path = os.path.join(os.path.dirname(current_script_dir), "prompts", filename)

        raise FileNotFoundError(
            f"Prompt file '{filename}' not found. \n"
            f"Expected at: {filepath} (relative to script: {current_script_dir})\n"
            f"Also checked CWD-based: {cwd_path} (CWD: {os.getcwd()})\n"
            f"Also checked project_root-based: {project_root_prompts_path}"
        )

    with open(filepath, "r", encoding="utf-8") as f:
        return f.read() 