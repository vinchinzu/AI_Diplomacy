"""
Utilities for loading prompts specific to the diplomacy game.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def load_diplomacy_prompt(filename: str) -> Optional[str]:
    """
    Loads a prompt template from the diplomacy prompts directory.

    Args:
        filename: The name of the prompt file (e.g., 'bloc_order_prompt.j2').

    Returns:
        The content of the file as a string, or None if an error occurs.
    """
    try:
        # This loader is specific to ai_diplomacy, so it knows the prompts are in ../prompts
        current_dir = os.path.dirname(os.path.abspath(__file__))
        prompts_dir = os.path.join(current_dir, "..", "prompts")
        filepath = os.path.join(prompts_dir, filename)

        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Diplomacy prompt file not found: {filepath}")
        return None
    except Exception as e:
        logger.error(f"Error loading diplomacy prompt file {filepath}: {e}")
        return None
