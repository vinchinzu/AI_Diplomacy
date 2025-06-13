"""
Defines strategies for constructing various prompts for LLM-based agents.

This module provides:
- BasePromptStrategy: An abstract base class for generic prompt strategies.
"""

import logging
from typing import Optional, Dict, Any

# Assuming llm_utils will be in the same generic framework package.
# This import is for BasePromptStrategy's _load_generic_system_prompt
from . import llm_utils  # Ensure this is available

logger = logging.getLogger(__name__)

__all__ = ["BasePromptStrategy"]


class BasePromptStrategy:
    """
    Base class for managing the construction of prompts for different LLM interaction types.
    Subclasses should implement specific prompt building logic.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        base_prompts_dir: Optional[str] = None,
    ):
        """
        Initializes the BasePromptStrategy.

        Args:
            config: A generic configuration dictionary.
            base_prompts_dir: Optional. Path to the base directory for prompts.
        """
        self.config = config or {}
        self.base_prompts_dir = base_prompts_dir
        self.system_prompt_template = self._load_generic_system_prompt()

    def _load_generic_system_prompt(self) -> str:
        """Loads a generic system prompt template from file or provides a default."""
        filename = self.config.get("system_prompt_filename", "generic_system_prompt.txt")
        prompt_content = llm_utils.load_prompt_file(filename, base_prompts_dir=self.base_prompts_dir)
        if prompt_content is None:
            logger.warning(f"Failed to load generic system prompt '{filename}'. Using a default prompt.")
            return "You are a helpful AI assistant."
        return prompt_content

    def _get_formatted_system_prompt(self, **kwargs) -> str:
        """Formats the system prompt with provided arguments."""
        try:
            return self.system_prompt_template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing key in system prompt formatting: {e}. Using raw template.")
            return self.system_prompt_template
        except Exception as e:
            logger.error(f"Error formatting system prompt: {e}. Using raw template.")
            return self.system_prompt_template

    def build_prompt(self, action_type: str, context: Dict[str, Any]) -> str:
        """
        Builds a prompt for a given action type and context.
        This is the primary method for generic agents.

        Args:
            action_type: A string identifying the type of action (e.g., "decide_action", "generate_communication").
            context: A dictionary containing all necessary information to build the prompt.

        Returns:
            The constructed prompt string.
        """
        raise NotImplementedError("Subclasses must implement build_prompt.")
