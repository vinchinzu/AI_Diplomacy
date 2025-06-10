"""
Utility functions for Large Language Model (LLM) interactions.

This module provides helper functions for loading prompt files, cleaning and
extracting JSON data from LLM text responses, and extracting specific
structured information like relationships and goals from parsed JSON.
"""

import os
import logging
import re
import json
from typing import Optional, Dict, Any, List # Added List
import csv # Added csv

import json_repair
import json5

logger = logging.getLogger(__name__)

__all__ = [
    "load_prompt_file",
    "clean_json_text",
    "extract_json_from_text",
    "extract_relationships",
    "extract_goals",
    "log_llm_response", # Added log_llm_response
]

# Constants for relationship extraction
REL_KEYS = ("updated_relationships", "relationships", "relationship_updates")


# Renamed from _load_prompt_file and moved from agent.py
def load_prompt_file(
    filename: str, base_prompts_dir: Optional[str] = None
) -> Optional[str]:
    """
    Loads a prompt template from the specified prompts directory.

    Args:
        filename: The name of the prompt file (e.g., 'system_prompt.txt').
        base_prompts_dir: Optional. The base directory where 'prompts' subdirectory is located.
                          If None, it defaults to the 'prompts' subdirectory within the
                          directory of this utility file (llm_utils.py).
    Returns:
        The content of the file as a string, or None if an error occurs.
    """
    try:
        if base_prompts_dir:
            prompts_dir = os.path.join(base_prompts_dir, "prompts")
        else:
            # Default to 'prompts' dir relative to this file (llm_utils.py)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            prompts_dir = os.path.join(current_dir, "prompts")

        filepath = os.path.join(prompts_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {filepath}")
        return None
    except Exception as e:
        logger.error(f"Error loading prompt file {filepath}: {e}")
        return None


# Moved from DiplomacyAgent class in agent.py
def clean_json_text(text: str) -> str:
    """Clean common JSON formatting issues from LLM responses."""
    if not text:
        return text

    # Remove trailing commas
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)

    # Fix newlines before JSON keys
    text = re.sub(r'\n\s+"(\w+)"\s*:', r'"\1":', text)

    # Remove comments (if any)
    text = re.sub(r"//.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)

    # Remove any BOM or zero-width spaces
    text = text.replace("\ufeff", "").replace("\u200b", "")

    return text.strip()


# Moved from DiplomacyAgent class in agent.py and adapted
def extract_json_from_text(
    text: str, logger_param: logging.Logger, identifier_for_log: str = ""
) -> Any:
    """
    Extract and parse JSON from text, handling common LLM response formats.
    Returns the parsed JSON object (usually a dict or list), or the original text if parsing fails.

    Args:
        text: The input string from which to extract JSON.
        logger_param: The logger instance to use for logging.
        identifier_for_log: A string to prepend to log messages for context (e.g., power name).

    Returns:
        A dictionary parsed from the JSON, or an empty dictionary if parsing fails.
    """
    if not text or not text.strip():
        logger_param.warning(
            f"{identifier_for_log} Empty text provided to JSON extractor"
        )
        return {}

    original_text = text

    # Preprocessing
    text = re.sub(r'\n\s+"(\w+)"\s*:', r'"\1":', text)
    problematic_patterns = [
        "negotiation_summary",
        "relationship_updates",
        "updated_relationships",
        "order_summary",
        "goals",
        "relationships",
        "intent",
    ]
    for (
        pattern_key
    ) in problematic_patterns:  # Renamed pattern to pattern_key to avoid conflict
        text = re.sub(rf'\n\s*"{pattern_key}"', f'"{pattern_key}"', text)

    patterns = [
        r"```\s*\{\{\s*(.*?)\s*\}\}\s*```",
        r"```(?:json)?\s*\n(.*?)\n\s*```",
        r"PARSABLE OUTPUT:\s*(\{.*?\})",
        r"JSON:\s*(\{.*?\})",
        r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})",
        r"`(\{.*?\})`",
    ]

    for pattern_str in patterns:
        match = re.search(pattern_str, text, re.DOTALL)
        if match:
            content_to_parse = match.group(1).strip()

            if (
                pattern_str == patterns[0]
                and content_to_parse
                and not content_to_parse.startswith("{")
                and not content_to_parse.endswith("}")
            ):
                # If it's the content from {{...}} and it's not already a JSON object string
                # try wrapping it to make it one. E.g. if content is '"key": "value"'
                potential_json_obj_str = "{" + content_to_parse + "}"
                try:
                    data = json.loads(potential_json_obj_str)
                    logger_param.debug(
                        f"{identifier_for_log} Successfully parsed content from '{{{{...}}}}' by wrapping: {pattern_str}"
                    )
                    return data
                except json.JSONDecodeError:
                    logger_param.debug(
                        f"{identifier_for_log} Wrapping content from '{{{{...}}}}' did not result in valid JSON. Proceeding with original content for further parsing/repair."
                    )
                    # Fall through to try parsing content_to_parse as is, then repair etc. on original content_to_parse

            try:
                cleaned = clean_json_text(content_to_parse)
                result = json.loads(cleaned)
                logger_param.debug(
                    f"{identifier_for_log} Successfully parsed JSON with pattern {pattern_str}"
                )
                return result
            except json.JSONDecodeError as e_initial:
                logger_param.debug(
                    f"{identifier_for_log} Standard JSON parse failed: {e_initial}"
                )

                try:
                    cleaned_match_candidate = content_to_parse
                    cleaned_match_candidate = re.sub(
                        r"\s*([A-Z][\w\s,]*?\.(?:\s+[A-Z][\w\s,]*?\.)*)\s*(?=[,\}\]])",
                        "",
                        cleaned_match_candidate,
                    )
                    cleaned_match_candidate = re.sub(
                        r"\s*([A-Z][\w\s,]*?\.(?:\s+[A-Z][\w\s,]*?\.)*)\s*(?=\s*\}\s*$)",
                        "",
                        cleaned_match_candidate,
                    )
                    cleaned_match_candidate = re.sub(
                        r'\n\s+"(\w+)"\s*:', r'"\1":', cleaned_match_candidate
                    )
                    cleaned_match_candidate = re.sub(
                        r",\s*}", "}", cleaned_match_candidate
                    )
                    for pp_key in problematic_patterns:  # Renamed pattern to pp_key
                        cleaned_match_candidate = cleaned_match_candidate.replace(
                            f'\n  "{pp_key}"', f'"{pp_key}"'
                        )
                    cleaned_match_candidate = re.sub(
                        r"'(\w+)'\s*:", r'"\1":', cleaned_match_candidate
                    )

                    if cleaned_match_candidate != content_to_parse:
                        logger_param.debug(
                            f"{identifier_for_log} Surgical cleaning applied. Attempting to parse modified JSON."
                        )
                        return json.loads(cleaned_match_candidate)
                except json.JSONDecodeError as e_surgical:
                    logger_param.debug(
                        f"{identifier_for_log} Surgical cleaning didn't work: {e_surgical}"
                    )

            try:
                result = json5.loads(content_to_parse)
                logger_param.debug(
                    f"{identifier_for_log} Successfully parsed with json5"
                )
                return result
            except Exception as e:
                logger_param.debug(f"{identifier_for_log} json5 parse failed: {e}")

            try:
                result = json_repair.loads(content_to_parse)
                logger_param.debug(
                    f"{identifier_for_log} Successfully parsed with json-repair"
                )
                return result
            except Exception as e:
                logger_param.debug(f"{identifier_for_log} json-repair failed: {e}")

    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            potential_json = text[start:end]
            for parser_name, parser_func in [
                ("json", json.loads),
                ("json5", json5.loads),
                ("json_repair", json_repair.loads),
            ]:
                try:
                    cleaned = (
                        clean_json_text(potential_json)
                        if parser_name == "json"
                        else potential_json
                    )
                    result = parser_func(cleaned)
                    logger_param.debug(
                        f"{identifier_for_log} Fallback parse succeeded with {parser_name}"
                    )
                    return result
                except Exception as e:
                    logger_param.debug(
                        f"{identifier_for_log} Fallback {parser_name} failed: {e}"
                    )

            try:
                cleaned_text = re.sub(r'[^{}[\]"\',:.\d\w\s_-]', "", potential_json)
                text_fixed = re.sub(r"'([^']*)':", r'"\1":', cleaned_text)
                text_fixed = re.sub(r": *\'([^\']*)\'", r': "\1"', text_fixed)
                result = json.loads(text_fixed)
                logger_param.debug(f"{identifier_for_log} Aggressive cleaning worked")
                return result
            except json.JSONDecodeError:
                pass  # logger_param.debug(f"{identifier_for_log} Aggressive cleaning failed")

    except Exception as e:
        logger_param.debug(f"{identifier_for_log} Fallback extraction failed: {e}")

    try:
        result = json_repair.loads(text)
        logger_param.warning(f"{identifier_for_log} Last resort json-repair succeeded")
        if not isinstance(result, dict):
            logger_param.error(
                f"{identifier_for_log} json-repair returned non-dict type: {type(result)}. Original text: {original_text[:500]}..."
            )
            return {}
        return result
    except Exception as e:
        logger_param.error(
            f"{identifier_for_log} All JSON extraction attempts failed. Original text: {original_text[:500]}... Error: {e}"
        )
        return {}


def extract_relationships(data) -> Optional[Dict[str, str]]:
    """
    Extract relationships from LLM response data, handling various key names.

    Args:
        data: Parsed JSON data from LLM response

    Returns:
        Dictionary of relationships if found, None otherwise
    """
    if not isinstance(data, dict):
        return None

    for key in REL_KEYS:
        if key in data and isinstance(data[key], dict):
            return data[key]
    return None


def extract_goals(data) -> Optional[list]:
    """
    Extract goals from LLM response data, handling various key names.

    Args:
        data: Parsed JSON data from LLM response

    Returns:
        List of goals if found, None otherwise
    """
    if not isinstance(data, dict):
        return None

    # Check various possible key names for goals
    goal_keys = ("updated_goals", "goals", "goal_updates")
    for key in goal_keys:
        if key in data and isinstance(data[key], list):
            return data[key]
    return None


# Moved from ai_diplomacy/general_utils.py
def log_llm_response(
    log_file_path: str,
    model_name: str,
    # Optional for non-power-specific calls like summary, but agent_id is more generic
    agent_id: Optional[str],
    phase: str,
    response_type: str,
    # raw_input_prompt: str, # Decided not to log the full prompt to save space
    raw_response: str,
    success: str,  # Assuming success is a string like "TRUE" or "FALSE: reason"
    request_identifier: Optional[str] = None, # Optional request identifier
    turn_number: Optional[int] = None, # Optional turn number
) -> None:
    """
    Log minimal LLM response metadata to a CSV file.

    Args:
        log_file_path: Path to the CSV log file.
        model_name: Name/ID of the LLM used.
        agent_id: Identifier of the agent making the call.
        phase: Current phase or step in the process.
        response_type: Type of response (e.g., "order_generation", "negotiation_analysis").
        raw_response: The raw text string received from the LLM.
        success: String indicating success status (e.g., "TRUE", "FALSE: error message").
        request_identifier: Optional unique ID for the request.
        turn_number: Optional turn number if applicable.
    """
    try:
        # Ensure directory exists
        log_dir = os.path.dirname(log_file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        log_fields = [
            "timestamp",
            "request_id",
            "turn",
            "model",
            "agent_id",
            "phase",
            "response_type",
            "success",
            "raw_response_excerpt", # Log an excerpt to keep file size manageable
        ]

        # Prepare excerpt
        # Using a constant for max length, defined in generic_llm_framework.constants
        # from . import constants as generic_constants # This would create a circular dependency if constants need llm_utils
        # For now, let's use a local sensible default or assume it's passed if critical.
        # Decided to use a hardcoded MAX_CONTENT_LOG_LENGTH for now to avoid import cycle.
        # Better would be to pass it from coordinator or have it in a base constants file.
        MAX_CONTENT_LOG_LENGTH = 500 # Matching the one in constants.py for now
        response_excerpt = (
            raw_response[:MAX_CONTENT_LOG_LENGTH] + "..."
            if len(raw_response) > MAX_CONTENT_LOG_LENGTH
            else raw_response
        )

        # Get current timestamp
        import datetime # Moved import here
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()


        log_row = [
            timestamp,
            request_identifier or "",
            str(turn_number) if turn_number is not None else "",
            model_name,
            agent_id or "",
            phase,
            response_type,
            success,
            response_excerpt,
        ]

        file_exists = os.path.isfile(log_file_path)
        with open(log_file_path, mode="a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            if not file_exists:
                writer.writerow(log_fields)
            writer.writerow(log_row)
    except Exception as e:
        # Use a logger specific to this module (llm_utils)
        logger.error(f"Failed to log LLM response to {log_file_path}: {e}", exc_info=True)
