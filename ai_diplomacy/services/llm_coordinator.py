"""
Centralized LLM coordination service.
Single entry point for all LLM calls with model pooling, serial locking, usage tracking, and retry logic.
"""

import asyncio

# Removed: import os
import logging
from typing import (
    Optional,
    Dict,
    Any,
    AsyncIterator,
    List,
    Callable,
    Awaitable,
)  # Removed Union, ContextManager
from contextlib import asynccontextmanager

# Removed: import json
import sqlite3  # Added import

# Removed: import functools

import llm  # Assuming this is the llm library by Simon Willison
from llm.models import (
    Model as LLMModel,
)  # Renamed to avoid conflict, used for type hinting
from llm import Response as LLMResponse  # For type hinting

from .. import constants # Import constants

logger = logging.getLogger(__name__)

__all__ = [
    "LLMCoordinator",
    "LLMCallResult",
    "ModelPool",
    "initialize_database",
    "record_usage",
    "get_usage_stats_by_country",
    "get_total_usage_stats",
    "get_global_coordinator", # To access the singleton instance
]

# --- New Global Components based on the provided pattern ---

DATABASE_PATH = constants.LLM_USAGE_DATABASE_PATH # Updated to use constant
_local_lock = asyncio.Lock()  # Removed comment: Global lock for local LLM engines


class ModelPool:
    """Caches LLM model instances."""

    _cache: Dict[str, LLMModel] = {}

    @classmethod
    def get(cls, model_id: str) -> LLMModel:
        """Retrieves a model from the cache, loading if not present."""
        if model_id not in cls._cache:
            logger.debug(f"[ModelPool] Loading and caching model: {model_id}")
            cls._cache[model_id] = llm.get_async_model(model_id)
        else:
            logger.debug(f"[ModelPool] Retrieving model from cache: {model_id}")
        return cls._cache[model_id]


@asynccontextmanager
async def serial_if_local(model_id: str) -> AsyncIterator[None]:
    """
    Context manager to serialize access to local LLMs (ollama, llamacpp).
    """
    model_id_lower = model_id.lower()
    # Case-insensitive check will be applied to these prefixes
    # These prefixes are taken from the original SERIAL_ACCESS_PREFIXES
    if any(model_id_lower.startswith(prefix) for prefix in constants.LOCAL_LLM_SERIAL_ACCESS_PREFIXES):
        logger.debug(f"Acquiring lock for local model: {model_id}")
        async with _local_lock:
            logger.debug(f"Lock acquired for local model: {model_id}")
            yield
            logger.debug(f"Lock released for local model: {model_id}")
    else:
        yield


def initialize_database():
    """Initializes the SQLite database and creates the 'usage' table if it doesn't exist."""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                """
            CREATE TABLE IF NOT EXISTS usage (
              id          INTEGER PRIMARY KEY,
              game_id     TEXT,
              agent       TEXT,
              phase       TEXT,
              model       TEXT,
              input       INTEGER,
              output      INTEGER,
              ts          DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS usage_game_agent ON usage (game_id, agent);"
            )
            conn.commit()
        logger.info(f"Database initialized successfully at {DATABASE_PATH}")
    except sqlite3.Error as e:
        logger.error(f"Error initializing database {DATABASE_PATH}: {e}", exc_info=True)
        raise


initialize_database()  # Removed comment: Initialize DB on module load


async def record_usage(game_id: str, agent: str, phase: str, response: LLMResponse):
    """Records LLM token usage in the database."""
    try:
        usage_stats = (
            await response.usage()
        )  # Usage(input=..., output=..., details=...)
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.execute(
                "INSERT INTO usage (game_id, agent, phase, model, input, output) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    game_id,
                    agent,
                    phase,
                    response.model.model_id,
                    usage_stats.input,
                    usage_stats.output,
                ),
            )
            conn.commit()
        logger.debug(
            f"Usage recorded for {agent} in game {game_id}, phase {phase}: {usage_stats.input} in, {usage_stats.output} out for model {response.model.model_id}"
        )
    except sqlite3.Error as e:
        logger.error(f"SQLite error in record_usage: {e}", exc_info=True)
    except AttributeError as e:
        model_id_for_log = "N/A"
        if hasattr(response, 'model') and response.model is not None:
            if hasattr(response.model, 'model_id'):
                model_id_for_log = response.model.model_id
            else:
                model_id_for_log = "Unknown (model_id attribute missing)"
        elif hasattr(response, 'model') and response.model is None:
            model_id_for_log = "N/A (response.model is None)"

        logger.error(
            f"Error accessing response attributes in record_usage (model: {model_id_for_log}): {e}",
            exc_info=True,
        )
    except Exception as e:
        logger.error(f"Unexpected error in record_usage: {e}", exc_info=True)


def get_usage_stats_by_country(game_id: str) -> Dict[str, Dict[str, int]]:
    """Get API usage statistics by country for a specific game."""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.execute(
                """
                SELECT agent, 
                       COUNT(*) as api_calls,
                       SUM(input) as total_input_tokens,
                       SUM(output) as total_output_tokens,
                       model
                FROM usage 
                WHERE game_id = ? 
                GROUP BY agent, model
                ORDER BY agent
            """,
                (game_id,),
            )

            results = {}
            for row in cursor.fetchall():
                agent, api_calls, input_tokens, output_tokens, model = row
                if agent not in results:
                    results[agent] = {
                        "api_calls": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "models": [],
                    }
                results[agent]["api_calls"] += api_calls
                results[agent]["input_tokens"] += input_tokens or 0
                results[agent]["output_tokens"] += output_tokens or 0
                if model not in results[agent]["models"]:
                    results[agent]["models"].append(model)

            return results
    except sqlite3.Error as e:
        logger.error(f"Error getting usage stats: {e}", exc_info=True)
        return {}


def get_total_usage_stats(game_id: str) -> Dict[str, int]:
    """Get total API usage statistics for a specific game."""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*) as total_api_calls,
                       SUM(input) as total_input_tokens,
                       SUM(output) as total_output_tokens
                FROM usage 
                WHERE game_id = ?
            """,
                (game_id,),
            )

            row = cursor.fetchone()
            if row:
                return {
                    "total_api_calls": row[0],
                    "total_input_tokens": row[1] or 0,
                    "total_output_tokens": row[2] or 0,
                }
            return {
                "total_api_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
            }
    except sqlite3.Error as e:
        logger.error(f"Error getting total usage stats: {e}", exc_info=True)
        return {"total_api_calls": 0, "total_input_tokens": 0, "total_output_tokens": 0}


async def llm_call_internal(
    game_id: str,
    agent_name: str,
    phase_str: str,
    model_id: str,
    prompt: str,
    system_prompt: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """
    Internal wrapper for LLM calls incorporating model pooling, serial locking, and usage recording.
    """
    model_obj = ModelPool.get(model_id)

    prompt_options: Dict[str, Any] = {}
    if system_prompt:
        prompt_options["system"] = system_prompt
    prompt_options.update(kwargs)

    async with serial_if_local(model_id):
        response_obj = model_obj.prompt(prompt, **prompt_options)

        # Ensure we wait for the text to be fully generated.
        response_text = await response_obj.text()

        # Record usage after getting the response (fire-and-forget)
        asyncio.create_task(record_usage(game_id, agent_name, phase_str, response_obj))

        return response_text


# --- End of New Global Components ---

# _local_llm_lock = asyncio.Lock() # Removed, use _local_lock

# Case-insensitive check will be applied to these prefixes
# SERIAL_ACCESS_PREFIXES = ["ollama/", "llamacpp/"] # Removed
# SERIALIZE_LOCAL_LLMS_ENV_VAR = "SERIALIZE_LOCAL_LLMS" # Removed


class LLMCallResult:
    """Structured result from an LLM call with parsing."""

    def __init__(
        self,
        raw_response: str,
        parsed_json: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: str = constants.LLM_CALL_RESULT_ERROR_NOT_INITIALIZED, # Default error message
    ):
        self.raw_response = raw_response
        self.parsed_json = parsed_json
        self.success = success
        self.error_message = error_message

    def get_field(self, *field_names: str) -> Optional[Any]:
        """Get the first available field from the parsed JSON."""
        if not self.parsed_json:
            return None

        for field_name in field_names:
            if field_name in self.parsed_json:
                return self.parsed_json[field_name]
        return None


class LLMCoordinator:
    """
    Coordinates requests to LLMs, incorporating model pooling, serial access for local models,
    and usage tracking. Single entry point for all LLM interactions.
    """

    def __init__(self):
        """Initialize the LLM coordinator."""
        logger.info("LLMCoordinator initialized.")

    async def call_text(
        self,
        prompt: str,
        *,
        model_id: str,
        agent_id: str,
        game_id: str = constants.DEFAULT_GAME_ID, # Updated to use constant
        phase: str = constants.DEFAULT_PHASE_NAME, # Updated to use constant
        system_prompt: Optional[str] = None,
        llm_caller_override: Optional[Callable[..., Awaitable[str]]] = None,
    ) -> str:
        """
        Simple text completion call.

        Args:
            prompt: The prompt text
            model_id: LLM model identifier
            agent_id: Agent identifier for tracking
            game_id: Game identifier for tracking
            phase: Game phase for tracking
            system_prompt: Optional system prompt
            llm_caller_override: Optional override for the LLM call logic.

        Returns:
            The raw text response
        """
        if llm_caller_override:
            return await llm_caller_override(
                game_id=game_id,
                agent_name=agent_id,
                phase_str=phase,
                model_id=model_id,
                prompt=prompt,
                system_prompt=system_prompt,
            )
        else:
            return await llm_call_internal(
                game_id=game_id,
                agent_name=agent_id,
                phase_str=phase,
                model_id=model_id,
                prompt=prompt,
                system_prompt=system_prompt,
            )

    async def call_json(
        self,
        prompt: str,
        *,
        model_id: str,
        agent_id: str,
        game_id: str = constants.DEFAULT_GAME_ID, # Updated to use constant
        phase: str = constants.DEFAULT_PHASE_NAME, # Updated to use constant
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        expected_fields: Optional[List[str]] = None,
        llm_caller_override: Optional[Callable[..., Awaitable[str]]] = None,
    ) -> Dict[str, Any]:
        """
        JSON completion call with parsing and validation.

        Args:
            prompt: The prompt text
            model_id: LLM model identifier
            agent_id: Agent identifier for tracking
            game_id: Game identifier for tracking
            phase: Game phase for tracking
            system_prompt: Optional system prompt
            tools: Optional tool definitions for MCP-capable models
            expected_fields: Optional list of required JSON fields
            llm_caller_override: Optional override for the LLM call logic.

        Returns:
            Parsed JSON response

        Raises:
            ValueError: If JSON parsing fails or required fields are missing
        """
        # TODO: Implement tool calling logic for MCP in Stage 3
        if tools:
            logger.debug(
                f"Tools provided but MCP not yet implemented: {len(tools)} tools"
            )

        result = await self.call_llm_with_json_parsing(
            model_id=model_id,
            prompt=prompt,
            system_prompt=system_prompt,
            game_id=game_id,
            agent_name=agent_id,
            phase_str=phase,
            expected_json_fields=expected_fields,
            llm_caller_override=llm_caller_override,
        )

        if not result.success:
            raise ValueError(f"LLM call failed: {result.error_message}")

        return result.parsed_json or {}

    async def call_llm_with_json_parsing(
        self,
        model_id: str,
        prompt: str,
        game_id: str,
        agent_name: str,
        phase_str: str,
        system_prompt: Optional[str] = None,
        request_identifier: str = constants.LLM_CALL_REQUEST_ID_DEFAULT, # Default request ID
        expected_json_fields: Optional[list] = None,
        response_type: str = constants.LLM_CALL_LOG_RESPONSE_TYPE_DEFAULT, # Default response type for logging
        log_to_file_path: Optional[str] = None,
        llm_caller_override: Optional[Callable[..., Awaitable[str]]] = None,
    ) -> LLMCallResult:
        """
        Internal method for LLM calls with JSON parsing.
        Used by call_json().
        """
        from .. import llm_utils  # Import here to avoid circular imports
        from ..general_utils import (
            log_llm_response,
        )  # Assuming this is still used for file logging

        result = LLMCallResult("", None, False, constants.LLM_CALL_RESULT_ERROR_NOT_INITIALIZED) # Use constant

        try:
            logger.info(
                f"[{request_identifier}] Preparing LLM call. "
                f"Game: {game_id}, Agent: {agent_name}, Phase: {phase_str}, Model: {model_id}"
            )

            if llm_caller_override:
                raw_response = await llm_caller_override(
                    game_id=game_id,
                    agent_name=agent_name,
                    phase_str=phase_str,
                    model_id=model_id,
                    prompt=prompt,
                    system_prompt=system_prompt,
                )
            else:
                raw_response = await llm_call_internal(
                    game_id=game_id,
                    agent_name=agent_name,
                    phase_str=phase_str,
                    model_id=model_id,
                    prompt=prompt,
                    system_prompt=system_prompt,
                )

            result.raw_response = raw_response

            if raw_response and raw_response.strip():
                try:
                    parsed_data = llm_utils.extract_json_from_text(
                        raw_response, logger, f"[{request_identifier}] JSON Parsing"
                    )
                    result.parsed_json = parsed_data
                    result.success = True
                    result.error_message = ""

                    # Validate expected fields if provided
                    if expected_json_fields and isinstance(parsed_data, dict):
                        missing_fields = [
                            field
                            for field in expected_json_fields
                            if field not in parsed_data
                        ]
                        if missing_fields:
                            result.success = False
                            result.error_message = (
                                f"Missing expected fields: {missing_fields}"
                            )

                except Exception as e:
                    logger.error(
                        f"[{request_identifier}] JSON parsing failed: {e}",
                        exc_info=True,
                    )
                    result.success = False
                    result.error_message = f"JSON parsing error: {e}"
            else:
                result.success = False
                result.error_message = constants.LLM_CALL_ERROR_EMPTY_RESPONSE # Use constant

        except Exception as e:
            logger.error(f"[{request_identifier}] LLM call failed: {e}", exc_info=True)
            result.success = False
            result.error_message = f"LLM call error: {e}"
            if not result.raw_response:
                result.raw_response = f"Error: {e}"

        # Log the full prompt/response to file if path provided
        if log_to_file_path and agent_name and phase_str:
            success_status = (
                "TRUE" if result.success else f"FALSE: {result.error_message}"
            )
            log_llm_response(
                log_file_path=log_to_file_path,
                model_name=model_id,
                power_name=agent_name,
                phase=phase_str,
                response_type=response_type,
                raw_input_prompt=prompt,
                raw_response=result.raw_response,
                success=success_status,
            )

        return result

    async def request(
        self,
        model_id: str,
        prompt_text: str,
        system_prompt_text: Optional[str],
        # New parameters for llm_call_internal
        game_id: str,
        agent_name: str,  # Was implicitly part of request_identifier before, now explicit
        phase_str: str,  # New explicit parameter
        request_identifier: str = constants.LLM_CALL_REQUEST_ID_DEFAULT,  # For coordinator's logging
        llm_caller_override: Optional[Callable[..., Awaitable[str]]] = None,
    ) -> str:
        """
        Makes a request to the specified LLM using the new internal wrapper.
        Handles model pooling, serial locking for local models, and DB-based usage logging.

        Args:
            model_id: The ID of the LLM to use (e.g., "ollama/llama3", "gpt-4o").
            prompt_text: The main prompt text for the LLM.
            system_prompt_text: Optional system prompt text.
            game_id: Game identifier for DB logging and context.
            agent_name: Agent/Power name for DB logging and context.
            phase_str: Game phase for DB logging and context.
            request_identifier: An identifier for the coordinator's logging purposes.
            llm_caller_override: Optional override for the LLM call logic.

        Returns:
            The text response from the LLM.

        Raises:
            Exception: Propagates exceptions from llm_call_internal.
        """
        logger.debug(
            f"[{request_identifier}] LLMCoordinator.request initiated. Model: {model_id}, Game: {game_id}, Agent: {agent_name}, Phase: {phase_str}"
        )
        logger.debug(
            f"[LLMCoordinator] Using model_id: {model_id}, system_prompt: {'Yes' if system_prompt_text else 'No'}"
        )
        logger.debug(
            f"[LLMCoordinator] Prompt (first 200 chars): {prompt_text[:200]}..."
        )

        try:
            if llm_caller_override:
                response_text = await llm_caller_override(
                    game_id=game_id,
                    agent_name=agent_name,
                    phase_str=phase_str,
                    model_id=model_id,
                    prompt=prompt_text,
                    system_prompt=system_prompt_text,
                )
            else:
                response_text = await llm_call_internal(
                    game_id=game_id,
                    agent_name=agent_name,
                    phase_str=phase_str,
                    model_id=model_id,
                    prompt=prompt_text,
                    system_prompt=system_prompt_text,
                )

            logger.info(
                f"[{request_identifier}] LLM call for {model_id} (Game: {game_id}, Agent: {agent_name}) succeeded via llm_call_internal."
            )
            logger.debug(
                f"[{request_identifier}] Received response from '{model_id}'. Response length: {len(response_text)}"
            )
            return response_text

        except Exception as e:
            logger.error(
                f"[{request_identifier}] Error during LLM request via llm_call_internal to '{model_id}' (Game: {game_id}, Agent: {agent_name}): {type(e).__name__}: {e}",
                exc_info=True,
            )
            raise

    async def get_model(
        self, model_id: str
    ) -> LLMModel:  # Renamed from get_model_for_power
        """Retrieves an LLM model instance using the ModelPool."""
        # power_name argument removed as ModelPool is global
        logger.debug(f"Requesting model: {model_id} via ModelPool")
        try:
            model_obj = ModelPool.get(model_id)
            logger.debug(f"Successfully retrieved model: {model_id} from ModelPool")
            return model_obj
        except Exception as e:
            logger.error(
                f"Failed to get model {model_id} via ModelPool: {e}", exc_info=True
            )
            raise

    # execute_llm_call method removed as it was a simple wrapper for request


# Initialize database on module load
initialize_database()

# Global coordinator instance
_global_coordinator = LLMCoordinator()

def get_global_coordinator() -> LLMCoordinator:
    """Returns the global singleton instance of LLMCoordinator."""
    return _global_coordinator
