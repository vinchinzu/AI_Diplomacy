import os
import logging
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI
from anthropic import Anthropic
from google import genai
from openai import OpenAI as DeepSeekOpenAI

logger = logging.getLogger(__name__)

load_dotenv()

def load_model_client(model_id: str, power_name: Optional[str] = None, emptysystem: bool = False) -> 'BaseModelClient':
    """
    Returns the appropriate LLM client for a given model_id string, optionally keyed by power_name.
    Example usage:
       client = load_model_client("claude-3-5-sonnet-20241022", power_name="FRANCE", emptysystem=True)
    """
    # Import here to avoid circular imports
    from .clients import ClaudeClient, GeminiClient, DeepSeekClient, OpenAIClient
    
    lower_id = model_id.lower()
    if "claude" in lower_id:
        return ClaudeClient(model_id, power_name, emptysystem=emptysystem)
    elif "gemini" in lower_id:
        return GeminiClient(model_id, power_name, emptysystem=emptysystem)
    elif "deepseek" in lower_id:
        return DeepSeekClient(model_id, power_name, emptysystem=emptysystem)
    else:
        # Default to OpenAI
        return OpenAIClient(model_id, power_name) 