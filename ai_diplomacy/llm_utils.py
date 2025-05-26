import os
import logging
import re
import json
from typing import Optional, Dict

import json_repair
import json5

logger = logging.getLogger(__name__) # Removed comment: # Logger for this module

# Constants for relationship extraction
REL_KEYS = ('updated_relationships', 'relationships', 'relationship_updates')

# Renamed from _load_prompt_file and moved from agent.py
def load_prompt_file(filename: str, base_prompts_dir: Optional[str] = None) -> Optional[str]:
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
            prompts_dir = os.path.join(base_prompts_dir, 'prompts')
        else:
            # Default to 'prompts' dir relative to this file (llm_utils.py)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            prompts_dir = os.path.join(current_dir, 'prompts')

        filepath = os.path.join(prompts_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
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
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)
    
    # Fix newlines before JSON keys
    text = re.sub(r'\n\s+"(\w+)"\s*:', r'"\1":', text)
    
    # Replace single quotes with double quotes for keys
    text = re.sub(r"'(\w+)'\s*:", r'"\1":', text)
    
    # Remove comments (if any)
    text = re.sub(r'//.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    
    # Fix unescaped quotes in values (basic attempt)
    # This is risky but sometimes helps with simple cases
    text = re.sub(r':\s*"([^"]*)"([^",}\]]+)"', r': "\1\2"', text)
    
    # Remove any BOM or zero-width spaces
    text = text.replace('\ufeff', '').replace('\u200b', '')
    
    return text.strip()

# Moved from DiplomacyAgent class in agent.py and adapted
def extract_json_from_text(text: str, logger_param: logging.Logger, identifier_for_log: str = "") -> Dict:
    """
    Extract and parse JSON from text, handling common LLM response formats.

    Args:
        text: The input string from which to extract JSON.
        logger_param: The logger instance to use for logging.
        identifier_for_log: A string to prepend to log messages for context (e.g., power name).

    Returns:
        A dictionary parsed from the JSON, or an empty dictionary if parsing fails.
    """
    if not text or not text.strip():
        logger_param.warning(f"{identifier_for_log} Empty text provided to JSON extractor")
        return {}
            
    original_text = text
    
    # Preprocessing
    text = re.sub(r'\n\s+"(\w+)"\s*:', r'"\1":', text)
    problematic_patterns = [
        'negotiation_summary', 'relationship_updates', 'updated_relationships',
        'order_summary', 'goals', 'relationships', 'intent'
    ]
    for pattern_key in problematic_patterns: # Renamed pattern to pattern_key to avoid conflict
        text = re.sub(fr'\n\s*"{pattern_key}"', f'"{pattern_key}"', text)
    
    patterns = [
        r"```\s*\{\{\s*(.*?)\s*\}\}\s*```",
        r"```(?:json)?\s*\n(.*?)\n\s*```",
        r"PARSABLE OUTPUT:\s*(\{.*?\})",
        r"JSON:\s*(\{.*?\})",
        r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})",
        r"`(\{.*?\})`",
    ]
    
    for pattern_idx, current_pattern in enumerate(patterns): # Renamed pattern to current_pattern
        matches = re.findall(current_pattern, text, re.DOTALL)
        if matches:
            for match_idx, match in enumerate(matches):
                json_text = match.strip()
                
                try:
                    cleaned = clean_json_text(json_text) # Use standalone clean_json_text
                    result = json.loads(cleaned)
                    logger_param.debug(f"{identifier_for_log} Successfully parsed JSON with pattern {pattern_idx}, match {match_idx}")
                    return result
                except json.JSONDecodeError as e_initial:
                    logger_param.debug(f"{identifier_for_log} Standard JSON parse failed: {e_initial}")
                    
                    try:
                        cleaned_match_candidate = json_text
                        cleaned_match_candidate = re.sub(r'\s*([A-Z][\w\s,]*?\.(?:\s+[A-Z][\w\s,]*?\.)*)\s*(?=[,\}\]])', '', cleaned_match_candidate)
                        cleaned_match_candidate = re.sub(r'\s*([A-Z][\w\s,]*?\.(?:\s+[A-Z][\w\s,]*?\.)*)\s*(?=\s*\}\s*$)', '', cleaned_match_candidate)
                        cleaned_match_candidate = re.sub(r'\n\s+"(\w+)"\s*:', r'"\1":', cleaned_match_candidate)
                        cleaned_match_candidate = re.sub(r',\s*}', '}', cleaned_match_candidate)
                        for pp_key in problematic_patterns: # Renamed pattern to pp_key
                            cleaned_match_candidate = cleaned_match_candidate.replace(f'\n  "{pp_key}"', f'"{pp_key}"')
                        cleaned_match_candidate = re.sub(r"'(\w+)'\s*:", r'"\1":', cleaned_match_candidate)

                        if cleaned_match_candidate != json_text:
                            logger_param.debug(f"{identifier_for_log} Surgical cleaning applied. Attempting to parse modified JSON.")
                            return json.loads(cleaned_match_candidate)
                    except json.JSONDecodeError as e_surgical:
                        logger_param.debug(f"{identifier_for_log} Surgical cleaning didn't work: {e_surgical}")
                
                try:
                    result = json5.loads(json_text)
                    logger_param.debug(f"{identifier_for_log} Successfully parsed with json5")
                    return result
                except Exception as e:
                    logger_param.debug(f"{identifier_for_log} json5 parse failed: {e}")
                
                try:
                    result = json_repair.loads(json_text)
                    logger_param.debug(f"{identifier_for_log} Successfully parsed with json-repair")
                    return result
                except Exception as e:
                    logger_param.debug(f"{identifier_for_log} json-repair failed: {e}")
    
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end > start:
            potential_json = text[start:end]
            for parser_name, parser_func in [
                ("json", json.loads),
                ("json5", json5.loads),
                ("json_repair", json_repair.loads)
            ]:
                try:
                    cleaned = clean_json_text(potential_json) if parser_name == "json" else potential_json
                    result = parser_func(cleaned)
                    logger_param.debug(f"{identifier_for_log} Fallback parse succeeded with {parser_name}")
                    return result
                except Exception as e:
                    logger_param.debug(f"{identifier_for_log} Fallback {parser_name} failed: {e}")
            
            try:
                cleaned_text = re.sub(r'[^{}[\]"\',:.\d\w\s_-]', '', potential_json)
                text_fixed = re.sub(r"'([^']*)':", r'"\1":', cleaned_text)
                text_fixed = re.sub(r': *\'([^\']*)\'', r': "\1"', text_fixed)
                result = json.loads(text_fixed)
                logger_param.debug(f"{identifier_for_log} Aggressive cleaning worked")
                return result
            except json.JSONDecodeError:
                pass # logger_param.debug(f"{identifier_for_log} Aggressive cleaning failed")
                
    except Exception as e:
        logger_param.debug(f"{identifier_for_log} Fallback extraction failed: {e}")
    
    try:
        result = json_repair.loads(text)
        logger_param.warning(f"{identifier_for_log} Last resort json-repair succeeded")
        return result
    except Exception as e:
        logger_param.error(f"{identifier_for_log} All JSON extraction attempts failed. Original text: {original_text[:500]}... Error: {e}")
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
    goal_keys = ('updated_goals', 'goals', 'goal_updates')
    for key in goal_keys:
        if key in data and isinstance(data[key], list):
            return data[key]
    return None
